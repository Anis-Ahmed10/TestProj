"""Unit tests for app/core/crypto.py — 100% coverage."""

import importlib
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

with patch("app.core.config.get_settings") as mock_settings:
    mock_settings.return_value.jira_token_encryption_key = Fernet.generate_key().decode()

    import app.core.crypto

    importlib.reload(app.core.crypto)

encrypt_token = app.core.crypto.encrypt_token
decrypt_token = app.core.crypto.decrypt_token


def test_encrypt_token_returns_different_string_than_input():
    token = "super-secret-jira-token"
    encrypted = encrypt_token(token)
    assert isinstance(encrypted, str)
    assert encrypted != token


def test_decrypt_token_recovers_original_value():
    token = "super-secret-jira-token"
    encrypted = encrypt_token(token)
    assert decrypt_token(encrypted) == token


def test_encrypt_token_is_nondeterministic():
    token = "same-token"
    first = encrypt_token(token)
    second = encrypt_token(token)
    assert first != second
    assert decrypt_token(first) == token
    assert decrypt_token(second) == token


def test_decrypt_token_raises_on_invalid_ciphertext():
    with pytest.raises(InvalidToken):
        decrypt_token("not-a-valid-fernet-token")


def test_decrypt_token_raises_on_tampered_ciphertext():
    encrypted = encrypt_token("another-secret")
    tampered = encrypted[:-4] + ("A" * 4)
    with pytest.raises(InvalidToken):
        decrypt_token(tampered)


def test_encrypt_empty_string_round_trips():
    encrypted = encrypt_token("")
    assert decrypt_token(encrypted) == ""


def test_get_fernet_raises_when_key_not_configured():
    with patch("app.core.crypto.get_settings") as mock_settings:
        mock_settings.return_value.jira_token_encryption_key = ""
        with pytest.raises(RuntimeError, match="jira_token_encryption_key is not configured"):
            app.core.crypto.encrypt_token("some-token")


def test_get_fernet_raises_when_key_is_none():
    with patch("app.core.crypto.get_settings") as mock_settings:
        mock_settings.return_value.jira_token_encryption_key = None
        with pytest.raises(RuntimeError, match="jira_token_encryption_key is not configured"):
            app.core.crypto.decrypt_token("some-token")
