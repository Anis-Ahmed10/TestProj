from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.connection import build_connect_args, build_database_url, get_db
from app.core.connection import test_connection as check_test_connection


@patch("app.core.connection.get_settings")
def test_build_database_url(mock_settings):
    mock_settings.return_value = MagicMock(
        db_user="user",
        db_password="pass",
        db_host="localhost",
        db_port=5432,
        db_name="db",
    )

    url = build_database_url()

    assert "postgresql+psycopg2://" in url
    assert "user" in url


@patch("app.core.connection.get_settings")
def test_build_connect_args_with_ssl(mock_settings):
    # Real Settings, not a MagicMock — a mock answers for any attribute, so it
    # cannot tell a field that exists from one the code only wishes existed.
    mock_settings.return_value = Settings(db_sslmode="require", db_sslrootcert=None)

    assert build_connect_args() == {"sslmode": "require"}


@patch("app.core.connection.get_settings")
def test_build_connect_args_without_ssl(mock_settings):
    mock_settings.return_value = Settings(db_sslmode="", db_sslrootcert=None)

    assert build_connect_args() == {}


@patch("app.core.connection.SessionLocal")
def test_get_db_closes_session(mock_session):
    db = MagicMock()
    mock_session.return_value = db

    generator = get_db()

    next(generator)

    try:
        next(generator)
    except StopIteration:
        pass

    db.close.assert_called_once()


@patch("app.core.connection.postgres_session")
def test_test_connection(mock_session):
    db = MagicMock()

    ctx = MagicMock()
    ctx.__enter__.return_value = db
    ctx.__exit__.return_value = None

    mock_session.return_value = ctx

    assert check_test_connection() is True

    db.execute.assert_called_once()
    db.commit.assert_called_once()
