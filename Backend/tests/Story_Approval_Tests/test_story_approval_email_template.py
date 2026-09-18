"""Tests for the story approval email template builder."""

from __future__ import annotations

import unittest

from app.services.email_templates.story_approval import (
    build_approval_notification,
    build_decision_summary_notification,
)


class BuildApprovalNotificationTests(unittest.TestCase):
    """Verify build_approval_notification's subject/html/text output."""

    def test_returns_subject_with_project_name(self) -> None:
        subject, _html, _text = build_approval_notification(
            reviewer_emails=["reviewer@example.com"],
            requestor_name="Alice",
            project_name="Migration",
            story_count=3,
            approval_link="https://app.example.com/approvals",
        )

        self.assertIn("Migration", subject)

    def test_lists_all_reviewers_in_html_and_text(self) -> None:
        reviewers = ["reviewer1@example.com", "reviewer2@example.com"]

        _subject, html_body, text_body = build_approval_notification(
            reviewer_emails=reviewers,
            requestor_name="Alice",
            project_name="Migration",
            story_count=3,
            approval_link="https://app.example.com/approvals",
        )

        for reviewer in reviewers:
            self.assertIn(reviewer, html_body)
            self.assertIn(reviewer, text_body)
        self.assertIn("Assigned reviewers", html_body)
        self.assertIn("Assigned reviewers", text_body)

    def test_uses_singular_reviewer_label_for_one_recipient(self) -> None:
        _subject, html_body, text_body = build_approval_notification(
            reviewer_emails=["reviewer@example.com"],
            requestor_name="Alice",
            project_name="Migration",
            story_count=1,
            approval_link="https://app.example.com/approvals",
        )

        self.assertIn("Assigned reviewer:", html_body)
        self.assertIn("Assigned reviewer:", text_body)
        self.assertNotIn("Assigned reviewers", html_body)
        self.assertNotIn("Assigned reviewers", text_body)

    def test_includes_approval_link(self) -> None:
        link = "https://app.example.com/approvals"

        _subject, html_body, text_body = build_approval_notification(
            reviewer_emails=["reviewer@example.com"],
            requestor_name="Alice",
            project_name="Migration",
            story_count=1,
            approval_link=link,
        )

        self.assertIn(link, html_body)
        self.assertIn(link, text_body)

    def test_escapes_reviewer_email_in_html(self) -> None:
        _subject, html_body, _text = build_approval_notification(
            reviewer_emails=["<script>@example.com"],
            requestor_name="Alice",
            project_name="Migration",
            story_count=1,
            approval_link="https://app.example.com/approvals",
        )

        self.assertNotIn("<script>@example.com", html_body)
        self.assertIn("&lt;script&gt;@example.com", html_body)

    def test_escapes_requestor_and_project_name_in_html(self) -> None:
        _subject, html_body, _text = build_approval_notification(
            reviewer_emails=["reviewer@example.com"],
            requestor_name="<script>alert(1)</script>",
            project_name="<img src=x onerror=alert(1)>",
            story_count=1,
            approval_link="https://app.example.com/approvals",
        )

        self.assertNotIn("<script>alert(1)</script>", html_body)
        self.assertNotIn("<img src=x onerror=alert(1)>", html_body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_body)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html_body)

    def test_html_is_wrapped_in_shared_layout_chrome(self) -> None:
        _subject, html_body, _text = build_approval_notification(
            reviewer_emails=["reviewer@example.com"],
            requestor_name="Alice",
            project_name="Migration",
            story_count=1,
            approval_link="https://app.example.com/approvals",
        )

        self.assertIn("Infuse Platform", html_body)
        self.assertIn("automated notification", html_body)


class BuildDecisionSummaryNotificationTests(unittest.TestCase):
    """Cover the empty-list branches: a batch can be all-approved or all-rejected,
    and the section for the empty side must be omitted rather than rendered blank."""

    def test_omits_rejected_section_when_nothing_was_rejected(self) -> None:
        _subject, html_body, text_body = build_decision_summary_notification(
            submitter_name="Sam",
            project_name="Apollo",
            approved_keys=["S-1", "S-2"],
            rejected_keys=[],
            review_link="https://app.example.com/test-generator",
        )

        self.assertIn("Approved (2)", html_body)
        self.assertNotIn("Rejected (0)", html_body)
        self.assertIn("Rejected (0): none", text_body)
        self.assertNotIn("can be revised and re-submitted", text_body)

    def test_includes_revision_hint_when_something_was_rejected(self) -> None:
        _subject, html_body, text_body = build_decision_summary_notification(
            submitter_name="Sam",
            project_name="Apollo",
            approved_keys=[],
            rejected_keys=["S-3"],
            review_link="https://app.example.com/test-generator",
        )

        self.assertNotIn("Approved (0)", html_body)
        self.assertIn("Rejected (1)", html_body)
        self.assertIn("can be revised and re-submitted", text_body)
