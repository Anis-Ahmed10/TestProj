"""App-level envelope encryption for long-lived credentials (e.g. Jira API tokens)."""

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().jira_token_encryption_key
    if not key:
        raise RuntimeError("jira_token_encryption_key is not configured")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()
