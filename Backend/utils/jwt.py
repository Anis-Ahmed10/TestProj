"""JWT verification against Cognito's JWKS endpoint."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import PyJWTError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    settings = get_settings()
    url = (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com"
        f"/{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    try:
        resp = httpx.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("jwks_fetch_failed", exc_info=True)
        raise RuntimeError(
            "Cannot fetch Cognito JWKS — check COGNITO_USER_POOL_ID and network"
        ) from exc


def decode_jwt_payload(token: str) -> dict:
    settings = get_settings()
    issuer = (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com"
        f"/{settings.cognito_user_pool_id}"
    )
    try:
        header = jwt.get_unverified_header(token)
        keys = {k["kid"]: k for k in _get_jwks()["keys"]}
        if header["kid"] not in keys:
            # Cognito may have rotated its signing keys — refetch once before giving up
            _get_jwks.cache_clear()
            keys = {k["kid"]: k for k in _get_jwks()["keys"]}
        if header["kid"] not in keys:
            raise ValueError("Unknown token signing key")
        public_key = RSAAlgorithm.from_jwk(json.dumps(keys[header["kid"]]))
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=issuer,
        )
    except (PyJWTError, KeyError) as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
