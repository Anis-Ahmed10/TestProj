"""Tests for app/utils/jwt.py — 100% branch coverage."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.utils.jwt import _get_jwks, decode_jwt_payload


def test_get_jwks_calls_cognito_endpoint():
    """_get_jwks hits the Cognito JWKS URL and returns the parsed JSON."""
    _get_jwks.cache_clear()

    mock_settings = MagicMock()
    mock_settings.aws_region = "eu-west-1"
    mock_settings.cognito_user_pool_id = "eu-west-1_TestPool"

    fake_jwks = {"keys": [{"kid": "abc", "kty": "RSA"}]}
    mock_response = MagicMock()
    mock_response.json.return_value = fake_jwks

    with (
        patch("app.utils.jwt.get_settings", return_value=mock_settings),
        patch("app.utils.jwt.httpx.get", return_value=mock_response) as mock_get,
    ):
        result = _get_jwks()

    expected_url = (
        "https://cognito-idp.eu-west-1.amazonaws.com" "/eu-west-1_TestPool/.well-known/jwks.json"
    )
    mock_get.assert_called_once_with(expected_url, timeout=5)
    assert result == fake_jwks

    _get_jwks.cache_clear()


def test_get_jwks_network_error_raises_runtime_error():
    """A network failure logs the error and raises RuntimeError."""
    _get_jwks.cache_clear()

    mock_settings = MagicMock()
    mock_settings.aws_region = "eu-west-1"
    mock_settings.cognito_user_pool_id = "eu-west-1_TestPool"

    with (
        patch("app.utils.jwt.get_settings", return_value=mock_settings),
        patch("app.utils.jwt.httpx.get", side_effect=httpx.ConnectError("timeout")),
        patch("app.utils.jwt.logger") as mock_logger,
    ):
        with pytest.raises(RuntimeError, match="Cannot fetch Cognito JWKS") as exc_info:
            _get_jwks()

    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)
    mock_logger.error.assert_called_once_with("jwks_fetch_failed", exc_info=True)
    _get_jwks.cache_clear()


def test_get_jwks_http_error_raises_runtime_error():
    """A non-2xx HTTP response logs the error and raises RuntimeError."""
    _get_jwks.cache_clear()

    mock_settings = MagicMock()
    mock_settings.aws_region = "eu-west-1"
    mock_settings.cognito_user_pool_id = "eu-west-1_TestPool"

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    )

    with (
        patch("app.utils.jwt.get_settings", return_value=mock_settings),
        patch("app.utils.jwt.httpx.get", return_value=mock_response),
        patch("app.utils.jwt.logger") as mock_logger,
    ):
        with pytest.raises(RuntimeError, match="Cannot fetch Cognito JWKS") as exc_info:
            _get_jwks()

    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    mock_logger.error.assert_called_once_with("jwks_fetch_failed", exc_info=True)
    _get_jwks.cache_clear()


def _mock_settings():
    s = MagicMock()
    s.aws_region = "eu-west-1"
    s.cognito_user_pool_id = "eu-west-1_TestPool"
    s.cognito_client_id = "client123"
    return s


def test_decode_jwt_payload_happy_path():
    """Valid token with a known kid returns decoded claims."""
    settings = _mock_settings()
    kid = "key-1"
    raw_key = {"kid": kid, "kty": "RSA", "n": "abc", "e": "AQAB"}
    fake_claims = {"sub": "user-1", "email": "a@b.com"}

    mock_pub_key = MagicMock()

    with (
        patch("app.utils.jwt.get_settings", return_value=settings),
        patch("app.utils.jwt._get_jwks", return_value={"keys": [raw_key]}),
        patch("app.utils.jwt.jwt.get_unverified_header", return_value={"kid": kid}),
        patch("app.utils.jwt.RSAAlgorithm.from_jwk", return_value=mock_pub_key),
        patch("app.utils.jwt.jwt.decode", return_value=fake_claims),
    ):
        result = decode_jwt_payload("some.token.value")

    assert result == fake_claims


def test_decode_jwt_payload_unknown_kid_raises_value_error():
    """A kid that is not present in the JWKS raises ValueError."""
    settings = _mock_settings()

    with (
        patch("app.utils.jwt.get_settings", return_value=settings),
        patch("app.utils.jwt._get_jwks", return_value={"keys": [{"kid": "other"}]}),
        patch("app.utils.jwt.jwt.get_unverified_header", return_value={"kid": "missing"}),
    ):
        with pytest.raises(ValueError, match="Unknown token signing key"):
            decode_jwt_payload("bad.token.value")


def test_decode_jwt_payload_expired_signature_raises_value_error():
    """ExpiredSignatureError is converted to ValueError."""
    settings = _mock_settings()
    kid = "key-1"

    with (
        patch("app.utils.jwt.get_settings", return_value=settings),
        patch("app.utils.jwt._get_jwks", return_value={"keys": [{"kid": kid}]}),
        patch("app.utils.jwt.jwt.get_unverified_header", return_value={"kid": kid}),
        patch("app.utils.jwt.RSAAlgorithm.from_jwk", MagicMock()),
        patch("app.utils.jwt.jwt.decode", side_effect=ExpiredSignatureError("expired")),
    ):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_jwt_payload("expired.token")


def test_decode_jwt_payload_jwt_error_raises_value_error():
    """Generic InvalidTokenError is converted to ValueError."""
    settings = _mock_settings()
    kid = "key-1"

    with (
        patch("app.utils.jwt.get_settings", return_value=settings),
        patch("app.utils.jwt._get_jwks", return_value={"keys": [{"kid": kid}]}),
        patch("app.utils.jwt.jwt.get_unverified_header", return_value={"kid": kid}),
        patch("app.utils.jwt.RSAAlgorithm.from_jwk", MagicMock()),
        patch("app.utils.jwt.jwt.decode", side_effect=InvalidTokenError("bad sig")),
    ):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_jwt_payload("invalid.token")


def test_decode_jwt_payload_key_error_raises_value_error():
    """KeyError (e.g., missing 'kid' in header) is converted to ValueError."""
    settings = _mock_settings()

    with (
        patch("app.utils.jwt.get_settings", return_value=settings),
        patch("app.utils.jwt._get_jwks", return_value={"keys": [{"kid": "k"}]}),
        # Header dict missing "kid" key → KeyError when accessing header["kid"]
        patch("app.utils.jwt.jwt.get_unverified_header", return_value={}),
    ):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_jwt_payload("no-kid.token")
