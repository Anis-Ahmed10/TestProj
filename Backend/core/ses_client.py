"""Boto3 SES client factory."""

from __future__ import annotations

from typing import Any

import boto3

from app.core.config import get_settings


def get_ses_client() -> Any:
    """Return a boto3 SES client using the Lambda execution role credentials."""
    settings = get_settings()
    return boto3.client("ses", region_name=settings.aws_region)
