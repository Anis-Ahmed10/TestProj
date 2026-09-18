"""Tests for the test case generator API endpoint (currently a retained stub).

The route deliberately returns an empty result while the frontend calls the
Lambda directly; these tests pin that stub contract so a regression is visible
when the real service flow is re-enabled.
"""

from __future__ import annotations

import unittest

from app.api.v1.endpoints.test_case_generator import generate_test_cases
from app.schemas.common import SuccessResponse
from app.schemas.test_case_generator import TestCaseGenerationRequest

LOGIN_EMAIL_PASSWORD_DESCRIPTION = (
    "As a user, I want to be able to login to my account with email and password."
)


def _valid_request() -> TestCaseGenerationRequest:
    return TestCaseGenerationRequest(
        impactPrompt="Generate comprehensive authentication test cases.",
        contextDocuments=[
            {
                "documentId": "DOC-001",
                "title": "Authentication Business Rules",
                "link": "C:/files/authentication_business_rules.txt",
            }
        ],
        epics=[
            {
                "epicKey": "EPIC-AUTH-001",
                "epicSummary": "Authentication and Access Management",
                "stories": [
                    {
                        "storyKey": "AED-10",
                        "summary": "User Login with Email and Password",
                        "description": LOGIN_EMAIL_PASSWORD_DESCRIPTION,
                    }
                ],
            }
        ],
        settings={
            "format": "BDD (Given/When/Then)",
            "coverage": "Comprehensive (All paths)",
            "priority": "All High",
        },
    )


class TestCaseGeneratorEndpointTests(unittest.IsolatedAsyncioTestCase):
    """Verify the stub route shape and payload handling."""

    async def test_returns_standard_success_response(self) -> None:
        response = await generate_test_cases(_valid_request())

        self.assertIsInstance(response, SuccessResponse)
        self.assertEqual(response.message, "Test cases generated successfully")
        self.assertEqual(response.data, [])


if __name__ == "__main__":
    unittest.main()
