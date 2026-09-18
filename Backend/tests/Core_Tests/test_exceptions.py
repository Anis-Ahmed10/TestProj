from app.core.exceptions import (
    DatabaseOperationException,
    JiraAuthException,
    JiraFetchException,
    JiraPushException,
    SesEmailException,
)


def test_jira_auth_exception_defaults():
    exc = JiraAuthException()

    assert exc.status_code == 401
    assert exc.detail == "Jira authentication failed"


def test_jira_fetch_exception_defaults():
    exc = JiraFetchException()

    assert exc.status_code == 502
    assert exc.detail == "Could not reach Jira. It may be down or unreachable — please try again."


def test_database_operation_exception_defaults():
    exc = DatabaseOperationException()

    assert exc.status_code == 500
    assert exc.message == "Database operation failed"


def test_jira_push_exception_defaults():
    exc = JiraPushException()

    assert exc.code == "JIRA_PUSH_FAILED"
    assert exc.message == "Failed to push issue to Jira"


def test_ses_email_exception_defaults():
    exc = SesEmailException()

    assert exc.code == "SES_EMAIL_FAILED"
    assert exc.message == "Failed to send email notification"
    assert exc.status_code == 500


def test_ses_email_exception_custom_message():
    exc = SesEmailException("SES quota exceeded")

    assert exc.code == "SES_EMAIL_FAILED"
    assert exc.message == "SES quota exceeded"
