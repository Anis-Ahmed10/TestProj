"""AWS SES email service — generic, template-agnostic email sending.

Callers build (subject, html_body, text_body) via a template module under
app/services/email_templates/ and pass the result here to send.
"""

from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.ses_client import get_ses_client

logger = logging.getLogger(__name__)


class SesEmailService:
    """Send composed emails via AWS SES."""

    def send_email(
        self,
        *,
        recipients: list[str],
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """Send an email to all recipients.

        Returns True on success, False on failure (failure is logged,
        not raised, so the caller can decide how to handle it).
        """
        settings = get_settings()
        sender = settings.ses_sender_email

        if not sender:
            logger.error("ses_sender_email is not configured; skipping email")
            return False

        try:
            client = get_ses_client()
            client.send_email(
                Source=sender,
                Destination={"ToAddresses": recipients},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info(
                "ses_email_sent",
                extra={"recipients": recipients, "subject": subject},
            )
            return True
        except ClientError as exc:
            logger.exception(
                "ses_send_email_failed",
                extra={
                    "recipients": recipients,
                    "error_code": exc.response["Error"]["Code"],
                },
            )
            return False
