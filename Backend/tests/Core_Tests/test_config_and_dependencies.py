"""Tests for settings, dependency helpers, and provider factory wiring."""

import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

from pydantic import ValidationError

from app.api import dependencies
from app.core.config import Settings, get_settings
from app.services.clients import ClientService
from app.services.programmes import ProgrammesService
from app.services.projects import ProjectsService


class SettingsTests(unittest.TestCase):
    """Verify runtime settings behavior."""

    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_settings_normalize_log_level(self) -> None:
        settings = Settings(
            _env_file=None,
            log_level="debug",
            enable_file_logging=False,
            log_file_path=Path("logs/app.log"),
        )

        self.assertEqual(settings.log_level, "DEBUG")

    def test_settings_reject_invalid_log_level(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Settings(_env_file=None, log_level="verbose")

        self.assertIn("log_level must be one of", str(context.exception))

    def test_get_settings_uses_lru_cache(self) -> None:
        get_settings.cache_clear()

        with patch("app.core.config.Settings", return_value=sentinel.settings) as settings_cls:
            first = get_settings()
            second = get_settings()

        self.assertIs(first, sentinel.settings)
        self.assertIs(second, sentinel.settings)
        settings_cls.assert_called_once_with()

    def test_cors_origins_includes_cloudfront_url(self) -> None:
        settings = Settings(
            _env_file=None,
            cloudfront_url="https://example.cloudfront.net",
        )
        self.assertEqual(
            settings.cors_origins,
            [
                "http://localhost:3000",
                "https://example.cloudfront.net",
            ],
        )

    def test_cors_origins_excludes_blank_cloudfront_url(self) -> None:
        settings = Settings(
            _env_file=None,
            cloudfront_url="   ",
        )

        self.assertEqual(
            settings.cors_origins,
            ["http://localhost:3000"],
        )


class DependencyTests(unittest.TestCase):
    """Verify cached dependency constructors."""

    def test_get_app_settings_returns_cached_settings_dependency(self) -> None:
        with patch("app.api.dependencies.get_settings", return_value=sentinel.settings) as getter:
            settings = dependencies.get_app_settings()

        self.assertIs(settings, sentinel.settings)
        getter.assert_called_once_with()

    def test_get_push_to_jira_service_returns_service(self) -> None:
        from unittest.mock import sentinel

        from app.services.jiraService import JiraService

        service = dependencies.get_jira_service(db=sentinel.db_session)

        self.assertIsInstance(service, JiraService)

    def test_get_client_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_client_service(db=db_session)

        self.assertIsInstance(service, ClientService)
        self.assertIs(service.db, db_session)

    def test_get_programme_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_programme_service(db=db_session)

        self.assertIsInstance(service, ProgrammesService)
        self.assertIs(service.db, db_session)

    def test_get_project_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_project_service(db=db_session)

        self.assertIsInstance(service, ProjectsService)
        self.assertIs(service.db, db_session)

    def test_get_file_operations_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_file_operations_service(db=db_session)

        from app.services.file_operations import FileOperationsService

        self.assertIsInstance(service, FileOperationsService)
        self.assertIs(service.db, db_session)

    def test_get_request_authorizer_returns_db_authorizer_bound_to_db(self) -> None:
        from app.components.authorizer import DbAuthorizer

        db_session = sentinel.db_session

        authorizer = dependencies.get_request_authorizer(db=db_session)

        self.assertIsInstance(authorizer, DbAuthorizer)
        self.assertIs(authorizer._db, db_session)

    def test_get_request_authorizer_delegates_to_get_authorizer(self) -> None:
        db_session = sentinel.db_session

        with patch(
            "app.api.dependencies.get_authorizer", return_value=sentinel.authorizer
        ) as factory:
            authorizer = dependencies.get_request_authorizer(db=db_session)

        self.assertIs(authorizer, sentinel.authorizer)
        factory.assert_called_once_with(db_session)

    def test_get_story_approval_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_story_approval_service(db=db_session)

        from app.services.story_approval import StoryApprovalService

        self.assertIsInstance(service, StoryApprovalService)
        self.assertIs(service.db, db_session)

    def test_get_users_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_users_service(db=db_session)

        from app.services.users import UsersService

        self.assertIsInstance(service, UsersService)
        self.assertIs(service.db, db_session)

    def test_get_teams_service_returns_service_for_supplied_db(self) -> None:
        db_session = sentinel.db_session

        service = dependencies.get_teams_service(db=db_session)

        from app.services.teams import TeamsService

        self.assertIsInstance(service, TeamsService)
        self.assertIs(service.db, db_session)
