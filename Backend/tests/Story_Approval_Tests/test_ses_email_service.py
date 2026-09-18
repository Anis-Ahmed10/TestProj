"""Tests for the generic SES email service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


class SesEmailServiceTests(unittest.TestCase):
    """Verify SesEmailService.send_email behaviour."""

    @patch("app.services.ses_email_service.get_ses_client")
    @patch("app.services.ses_email_service.get_settings")
    def test_send_email_success(self, mock_settings, mock_client_fn) -> None:
        from app.services.ses_email_service import SesEmailService

        mock_settings.return_value = MagicMock(
            ses_sender_email="noreply@example.com",
        )
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "abc123"}
        mock_client_fn.return_value = mock_client

        service = SesEmailService()
        result = service.send_email(
            recipients=["reviewer1@example.com", "reviewer2@example.com"],
            subject="Test Subject",
            html_body="<p>hi</p>",
            text_body="hi",
        )

        self.assertTrue(result)
        mock_client.send_email.assert_called_once()
        call_kwargs = mock_client.send_email.call_args.kwargs
        self.assertEqual(call_kwargs["Source"], "noreply@example.com")
        self.assertEqual(
            call_kwargs["Destination"]["ToAddresses"],
            ["reviewer1@example.com", "reviewer2@example.com"],
        )
        self.assertEqual(call_kwargs["Message"]["Subject"]["Data"], "Test Subject")
        self.assertEqual(call_kwargs["Message"]["Body"]["Html"]["Data"], "<p>hi</p>")
        self.assertEqual(call_kwargs["Message"]["Body"]["Text"]["Data"], "hi")

    @patch("app.services.ses_email_service.get_ses_client")
    @patch("app.services.ses_email_service.get_settings")
    def test_send_email_handles_client_error(self, mock_settings, mock_client_fn) -> None:
        from app.services.ses_email_service import SesEmailService

        mock_settings.return_value = MagicMock(
            ses_sender_email="noreply@example.com",
        )
        mock_client = MagicMock()
        mock_client.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email rejected"}},
            "SendEmail",
        )
        mock_client_fn.return_value = mock_client

        service = SesEmailService()
        result = service.send_email(
            recipients=["reviewer@example.com"],
            subject="Test Subject",
            html_body="<p>hi</p>",
            text_body="hi",
        )

        self.assertFalse(result)

    @patch("app.services.ses_email_service.get_settings")
    def test_send_email_skips_when_sender_not_configured(self, mock_settings) -> None:
        from app.services.ses_email_service import SesEmailService

        mock_settings.return_value = MagicMock(ses_sender_email="")

        service = SesEmailService()
        result = service.send_email(
            recipients=["reviewer@example.com"],
            subject="Test Subject",
            html_body="<p>hi</p>",
            text_body="hi",
        )

        self.assertFalse(result)
