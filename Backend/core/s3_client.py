"""Boto3 S3 client factory."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from app.core.config import get_settings


def get_s3_client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )
