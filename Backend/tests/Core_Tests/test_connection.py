"""Tests for PostgreSQL connection helpers."""

import importlib
import runpy
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core import connection
from app.core.config import Settings


class _FakeSession:
    def __init__(self) -> None:
        self.execute = Mock()
        self.commit = Mock()
        self.close = Mock()


def test_build_database_url_uses_settings() -> None:
    settings = SimpleNamespace(
        db_user="alice",
        db_password="secret",
        db_host="db.internal",
        db_port=5432,
        db_name="clients",
    )

    with patch("app.core.connection.get_settings", return_value=settings):
        url = connection.build_database_url()

    assert url == "postgresql+psycopg2://alice:secret@db.internal:5432/clients"


# Real Settings, not a SimpleNamespace: a hand-rolled stub answers for any
# attribute, which is how DB_SSLMODE went unread for months while these passed.
def _settings(**overrides) -> Settings:
    return Settings(**{"db_sslmode": "", "db_sslrootcert": None, **overrides})


def test_build_connect_args_returns_sslmode_when_present() -> None:
    with patch("app.core.connection.get_settings", return_value=_settings(db_sslmode="require")):
        connect_args = connection.build_connect_args()

    assert connect_args == {"sslmode": "require"}


def test_build_connect_args_includes_root_cert_for_verify_full() -> None:
    settings = _settings(db_sslmode="verify-full", db_sslrootcert="/var/task/bundle.pem")

    with patch("app.core.connection.get_settings", return_value=settings):
        connect_args = connection.build_connect_args()

    assert connect_args == {
        "sslmode": "verify-full",
        "sslrootcert": "/var/task/bundle.pem",
    }


def test_build_connect_args_returns_empty_dict_when_missing() -> None:
    with patch("app.core.connection.get_settings", return_value=_settings()):
        connect_args = connection.build_connect_args()

    assert connect_args == {}


def test_create_postgres_engine_passes_expected_arguments() -> None:
    engine = object()

    with (
        patch("app.core.connection.build_database_url", return_value="db-url") as build_url,
        patch(
            "app.core.connection.build_connect_args", return_value={"sslmode": "require"}
        ) as build_args,
        patch("app.core.connection.create_engine", return_value=engine) as create_engine,
    ):
        result = connection.create_postgres_engine()

    assert result is engine
    build_url.assert_called_once_with()
    build_args.assert_called_once_with()
    create_engine.assert_called_once_with(
        "db-url",
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_recycle=900,
        connect_args={"sslmode": "require"},
    )


def test_get_db_closes_session() -> None:
    fake_session = _FakeSession()

    with patch("app.core.connection.SessionLocal", return_value=fake_session):
        generator = connection.get_db()
        yielded_session = next(generator)
        generator.close()

    assert yielded_session is fake_session
    fake_session.close.assert_called_once_with()


def test_postgres_session_closes_session() -> None:
    fake_session = _FakeSession()

    with patch("app.core.connection.SessionLocal", return_value=fake_session):
        with connection.postgres_session() as yielded_session:
            assert yielded_session is fake_session

    fake_session.close.assert_called_once_with()


def test_test_connection_executes_health_check_and_commits() -> None:
    fake_session = _FakeSession()

    @contextmanager
    def fake_postgres_session():
        yield fake_session

    with patch("app.core.connection.postgres_session", fake_postgres_session):
        assert connection.test_connection() is True

    fake_session.execute.assert_called_once()
    fake_session.commit.assert_called_once_with()


def test_test_connection_stores_version_string_when_scalar_returns_str() -> None:
    """Covers the `if isinstance(version, str)` true-branch in test_connection()."""
    fake_session = _FakeSession()
    version_str = "PostgreSQL 16.1"
    # Make scalar_one_or_none() return a real string
    fake_result = Mock()
    fake_result.scalar_one_or_none.return_value = version_str
    fake_session.execute.return_value = fake_result

    @contextmanager
    def fake_postgres_session():
        yield fake_session

    with patch("app.core.connection.postgres_session", fake_postgres_session):
        assert connection.test_connection() is True

    assert connection._last_connection_version == version_str


def test_main_prints_version_when_last_connection_version_is_set() -> None:
    """Covers the `if _last_connection_version:` true-branch in main()."""
    buffer = StringIO()
    with (
        patch("app.core.connection.test_connection", return_value=True),
        patch.object(connection, "_last_connection_version", "PostgreSQL 16.1"),
    ):
        with redirect_stdout(buffer):
            connection.main()

    output = buffer.getvalue()
    assert "Connected to PostgreSQL successfully." in output
    assert "PostgreSQL 16.1" in output


def test_main_prints_success_message_on_success() -> None:
    fake_session = _FakeSession()

    @contextmanager
    def fake_postgres_session():
        yield fake_session

    buffer = StringIO()
    with patch("app.core.connection.postgres_session", fake_postgres_session):
        with redirect_stdout(buffer):
            connection.main()

    fake_session.execute.assert_called_once()
    assert buffer.getvalue() == "Connected to PostgreSQL successfully.\n"


def test_main_prints_failure_message_on_error() -> None:
    class _RaisingSessionContext:
        def __enter__(self):
            raise RuntimeError("boom")

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_postgres_session():
        return _RaisingSessionContext()

    buffer = StringIO()
    with patch("app.core.connection.postgres_session", fake_postgres_session):
        with redirect_stdout(buffer):
            connection.main()

    assert "Failed to connect to PostgreSQL: boom" in buffer.getvalue()


def test_main_prints_nothing_when_test_connection_returns_false() -> None:
    buffer = StringIO()

    with patch("app.core.connection.test_connection", return_value=False):
        with redirect_stdout(buffer):
            connection.main()

    assert buffer.getvalue() == ""


def test_module_entrypoint_runs_main_block() -> None:
    fake_session = _FakeSession()

    def fake_sessionmaker(**_kwargs):
        return lambda: fake_session

    with (
        patch(
            "app.core.config.get_settings",
            return_value=SimpleNamespace(
                db_user="alice",
                db_password="secret",
                db_host="db.internal",
                db_port=5432,
                db_name="clients",
                db_sslmode="require",
                db_sslrootcert=None,
            ),
        ),
        patch("sqlalchemy.create_engine", return_value=object()),
        patch("sqlalchemy.orm.sessionmaker", side_effect=fake_sessionmaker),
    ):
        buffer = StringIO()
        with redirect_stdout(buffer):
            runpy.run_path(connection.__file__, run_name="__main__")

    output = buffer.getvalue()
    assert "Connected to PostgreSQL successfully." in output
    fake_session.execute.assert_called_once()


def test_module_reload_executes_import_path_without_main_block() -> None:
    fake_session = _FakeSession()

    def fake_sessionmaker(**_kwargs):
        return lambda: fake_session

    with (
        patch(
            "app.core.config.get_settings",
            return_value=SimpleNamespace(
                db_user="alice",
                db_password="secret",
                db_host="db.internal",
                db_port=5432,
                db_name="clients",
                db_sslmode="require",
                db_sslrootcert=None,
            ),
        ),
        patch("sqlalchemy.create_engine", return_value=object()),
        patch("sqlalchemy.orm.sessionmaker", side_effect=fake_sessionmaker),
    ):
        reloaded_connection = importlib.reload(connection)

    assert reloaded_connection is connection


def test_resolve_db_password_returns_the_configured_password() -> None:
    settings = SimpleNamespace(db_password="local-secret")

    with patch("app.core.connection.get_settings", return_value=settings):
        assert connection.resolve_db_password() == "local-secret"


def test_resolve_db_password_raises_when_unset() -> None:
    settings = SimpleNamespace(db_password=None)

    with patch("app.core.connection.get_settings", return_value=settings):
        with pytest.raises(RuntimeError, match="DB_PASSWORD"):
            connection.resolve_db_password()


def test_build_database_url_escapes_password() -> None:
    settings = SimpleNamespace(
        db_user="aei_app",
        db_host="rds.internal",
        db_port=5432,
        db_name="aeidb",
    )

    with (
        patch("app.core.connection.get_settings", return_value=settings),
        patch("app.core.connection.resolve_db_password", return_value="p@ss/w:rd"),
    ):
        url = connection.build_database_url()

    assert url == "postgresql+psycopg2://aei_app:p%40ss%2Fw%3Ard@rds.internal:5432/aeidb"
