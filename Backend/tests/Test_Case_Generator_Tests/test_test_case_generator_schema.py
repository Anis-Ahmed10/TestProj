"""Tests for test case generator schema validation."""

import unittest

from pydantic import ValidationError

from app.schemas.test_case_generator import (
    TestCaseGenerationBddTestCase,
    TestCaseGenerationData,
    TestCaseGenerationEpicResult,
    TestCaseGenerationMetadata,
    TestCaseGenerationRequest,
    TestCaseGenerationSettings,
    TestCaseGenerationStandardTestCase,
    TestCaseGenerationStoryResult,
    _normalize_coverage,
    _normalize_format,
    _normalize_priority,
    current_utc_isoformat,
)

LOGIN_EMAIL_PASSWORD_DESCRIPTION = (
    "As a user, I want to be able to login to my account with email and password."
)

EXPECTED_RESULT = (
    "User successfully logs into the application and receives authenticated session access"
)

ACCEPTANCE = "First criterion;\nSecond criterion\n\nThird criterion"


class TestCaseGenerationSettingsTests(unittest.TestCase):
    """Verify generation setting normalization."""

    def test_normalizes_supported_aliases(self) -> None:
        settings = TestCaseGenerationSettings(
            format="BDD (Given/When/Then)",
            coverage="Comprehensive (All paths)",
            priority="All High",
        )

        self.assertEqual(settings.format, "bdd")
        self.assertEqual(settings.coverage, "comprehensive")
        self.assertEqual(settings.priority, "all_high")

    def test_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_format("unsupported")

        self.assertIn("settings.format must be one of", str(context.exception))

    def test_rejects_unsupported_format(self) -> None:
        with self.assertRaises(ValueError) as context:
            TestCaseGenerationSettings(
                format="unsupported",
                coverage="Comprehensive (All paths)",
                priority="All High",
            )

        self.assertIn("BDD (Given/When/Then)", str(context.exception))

    def test_rejects_invalid_coverage(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_coverage("unsupported")

        self.assertIn("settings.coverage must be one of", str(context.exception))

    def test_rejects_invalid_priority(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_priority("unsupported")

        self.assertIn("settings.priority must be one of", str(context.exception))


class TestCaseGenerationRequestTests(unittest.TestCase):
    """Verify top-level request validation."""

    def test_accepts_blank_impact_prompt(self) -> None:
        request = TestCaseGenerationRequest(
            impactPrompt="   ",
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

        self.assertEqual(request.impact_prompt, "   ")

    def test_normalizes_none_context_documents_and_epics_before_validation(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationRequest(
                impactPrompt="Generate comprehensive authentication test cases.",
                contextDocuments=None,
                epics=None,
                settings={
                    "format": "BDD (Given/When/Then)",
                    "coverage": "Comprehensive (All paths)",
                    "priority": "All High",
                },
            )

        self.assertIn("Request must include epics", str(context.exception))

    def test_normalizes_none_epics_before_validation(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationRequest(
                impactPrompt="Generate comprehensive authentication test cases.",
                contextDocuments=[
                    {
                        "documentId": "DOC-001",
                        "title": "Authentication Business Rules",
                        "link": "C:/files/authentication_business_rules.txt",
                    }
                ],
                epics=None,
                settings={
                    "format": "BDD (Given/When/Then)",
                    "coverage": "Comprehensive (All paths)",
                    "priority": "All High",
                },
            )

        self.assertIn("Request must include epics", str(context.exception))

    def test_rejects_request_without_context_documents(self) -> None:
        with self.assertRaises(ValidationError):
            TestCaseGenerationRequest(
                impactPrompt="Generate comprehensive authentication test cases.",
                epics=[
                    {
                        "epicKey": "EPIC-AUTH-001",
                        "epicSummary": "Authentication and Access Management",
                        "stories": [
                            {
                                "storyKey": "AED-10",
                                "summary": "User Login with Email and Password",
                                "description": LOGIN_EMAIL_PASSWORD_DESCRIPTION,
                                "acceptanceCriteria": ["User can enter email and password"],
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

    def test_rejects_request_without_epics(self) -> None:
        with self.assertRaises(ValidationError):
            TestCaseGenerationRequest(
                impactPrompt="Generate comprehensive authentication test cases.",
                contextDocuments=[
                    {
                        "documentId": "DOC-001",
                        "title": "Authentication Business Rules",
                        "link": "C:/files/authentication_business_rules.txt",
                    }
                ],
                settings={
                    "format": "BDD (Given/When/Then)",
                    "coverage": "Comprehensive (All paths)",
                    "priority": "All High",
                },
            )

    def test_accepts_structured_payload(self) -> None:
        request = TestCaseGenerationRequest(
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
                            "acceptanceCriteria": ["User can enter email and password"],
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

        payload = request.model_dump(mode="json", by_alias=True)

        self.assertEqual(
            payload["impactPrompt"], "Generate comprehensive authentication test cases."
        )
        self.assertEqual(payload["contextDocuments"][0]["documentId"], "DOC-001")
        self.assertEqual(
            payload["contextDocuments"][0]["link"], "C:/files/authentication_business_rules.txt"
        )
        self.assertEqual(payload["epics"][0]["epicKey"], "EPIC-AUTH-001")
        self.assertEqual(payload["epics"][0]["stories"][0]["storyKey"], "AED-10")

    def test_accepts_story_without_acceptance_criteria(self) -> None:
        request = TestCaseGenerationRequest(
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

        payload = request.model_dump(mode="json", by_alias=True)

        self.assertEqual(payload["epics"][0]["stories"][0]["acceptanceCriteria"], [])


class TestCaseGenerationNestedInputValidationTests(unittest.TestCase):
    """Verify the nested input validators on the source models."""

    def test_rejects_blank_context_document_link(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationRequest(
                impactPrompt="Generate comprehensive authentication test cases.",
                contextDocuments=[
                    {
                        "documentId": "DOC-001",
                        "title": "Authentication Business Rules",
                        "link": "   ",
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

        self.assertIn("link cannot be empty", str(context.exception))

    def test_normalizes_string_tuple_and_list_acceptance_criteria(self) -> None:
        story = TestCaseGenerationRequest(
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
                            "acceptanceCriteria": (
                                "First criterion",
                                "",
                                "Second criterion",
                            ),
                        },
                        {
                            "storyKey": "AED-11",
                            "summary": "Password reset",
                            "description": "Password reset description",
                            "acceptanceCriteria": ["One", "", "Two", 3],
                        },
                    ],
                }
            ],
            settings={
                "format": "BDD (Given/When/Then)",
                "coverage": "Comprehensive (All paths)",
                "priority": "All High",
            },
        )

        payload = story.model_dump(mode="json", by_alias=True)

        self.assertEqual(
            payload["epics"][0]["stories"][0]["acceptanceCriteria"],
            [
                "First criterion",
                "Second criterion",
            ],
        )
        self.assertEqual(
            payload["epics"][0]["stories"][1]["acceptanceCriteria"],
            [
                "One",
                "Two",
                "3",
            ],
        )

    def test_normalizes_none_acceptance_criteria_to_empty_list(self) -> None:
        request = TestCaseGenerationRequest(
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
                            "acceptanceCriteria": None,
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

        payload = request.model_dump(mode="json", by_alias=True)

        self.assertEqual(payload["epics"][0]["stories"][0]["acceptanceCriteria"], [])

    def test_normalizes_string_acceptance_criteria_into_list(self) -> None:
        request = TestCaseGenerationRequest(
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
                            "acceptanceCriteria": ACCEPTANCE,
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

        payload = request.model_dump(mode="json", by_alias=True)

        self.assertEqual(
            payload["epics"][0]["stories"][0]["acceptanceCriteria"],
            [
                "First criterion",
                "Second criterion",
                "Third criterion",
            ],
        )

    def test_rejects_invalid_acceptance_criteria_type(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationRequest(
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
                                "acceptanceCriteria": {"invalid": True},
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

        self.assertIn(
            "acceptanceCriteria must be a string or an array of strings", str(context.exception)
        )

    def test_rejects_blank_story_and_epic_fields(self) -> None:
        with self.assertRaises(ValidationError) as story_context:
            TestCaseGenerationRequest(
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
                                "summary": "   ",
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

        self.assertIn("story text cannot be empty", str(story_context.exception))

        with self.assertRaises(ValidationError) as epic_context:
            TestCaseGenerationRequest(
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
                        "epicSummary": "   ",
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

        self.assertIn("epicSummary cannot be empty", str(epic_context.exception))


class TestCaseGenerationStructuredModelsTests(unittest.TestCase):
    """Verify the nested UI response models."""

    def test_rejects_blank_required_response_fields(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationStandardTestCase(
                testCaseId="   ",
                title="   ",
                type="Positive",
                expectedResult=EXPECTED_RESULT,
                steps=["Navigate to login page"],
            )

        self.assertIn("field cannot be empty", str(context.exception))

    def test_rejects_blank_optional_priority(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TestCaseGenerationStandardTestCase(
                testCaseId="TC-AED-10-001",
                title="Verify successful login",
                type="Positive",
                priority="   ",
                preconditions=["User account exists"],
                steps=["Navigate to login page"],
                expectedResult=EXPECTED_RESULT,
            )

        self.assertIn("field cannot be empty", str(context.exception))

    def test_allows_explicit_none_priority(self) -> None:
        test_case = TestCaseGenerationStandardTestCase(
            testCaseId="TC-AED-10-001",
            title="Verify successful login",
            type="Positive",
            priority=None,
            preconditions=["User account exists"],
            steps=["Navigate to login page"],
            expectedResult=EXPECTED_RESULT,
        )

        self.assertIsNone(test_case.priority)

    def test_current_utc_isoformat_returns_utc_timestamp(self) -> None:
        timestamp = current_utc_isoformat()

        self.assertTrue(timestamp.endswith("Z"))
        self.assertIn("T", timestamp)
        self.assertNotIn(".", timestamp)

    def test_nested_response_models_validate(self) -> None:
        data = TestCaseGenerationData(
            metadata=TestCaseGenerationMetadata(
                generatedAt="2026-05-11T10:30:00Z",
                format="BDD (Given/When/Then)",
                coverage="Comprehensive (All paths)",
                priorityMode="All High",
                totalEpics=2,
                totalStories=3,
                totalTestCases=28,
            ),
            generatedTestCases=[
                TestCaseGenerationEpicResult(
                    epicKey="EPIC-AUTH-001",
                    epicSummary="Authentication and Access Management",
                    stories=[
                        TestCaseGenerationStoryResult(
                            storyKey="AED-10",
                            storySummary="User Login with Email and Password",
                            testCases=[
                                TestCaseGenerationBddTestCase(
                                    testCaseId="TC-AED-10-001",
                                    title="Verify successful login with valid credentials",
                                    type="Positive",
                                    priority="High",
                                    preconditions=["User account exists", "User is on login page"],
                                    scenario={
                                        "given": "User is on login page",
                                        "when": "User enters valid email and valid password",
                                        "then": "User should be redirected to dashboard",
                                    },
                                    testData={
                                        "email": "user@example.com",
                                        "password": "ValidPassword123!",
                                    },
                                    expectedResult=EXPECTED_RESULT,
                                    tags=["authentication", "login", "positive"],
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        self.assertEqual(data.metadata.total_test_cases, 28)
        self.assertEqual(data.generated_test_cases[0].stories[0].test_cases[0].priority, "High")
        self.assertEqual(
            data.generated_test_cases[0].stories[0].test_cases[0].scenario["given"],
            "User is on login page",
        )
        self.assertFalse(hasattr(data.generated_test_cases[0].stories[0].test_cases[0], "steps"))

    def test_standard_response_models_validate_steps_only(self) -> None:
        test_case = TestCaseGenerationStandardTestCase(
            testCaseId="TC-AED-10-001",
            title="Verify successful login",
            type="Positive",
            priority="High",
            preconditions=["User account exists"],
            steps=["Navigate to login page", "Enter valid email", "Click login button"],
            expectedResult="User is redirected to dashboard",
            tags=["authentication"],
        )

        self.assertEqual(test_case.steps[0], "Navigate to login page")
        self.assertFalse(hasattr(test_case, "scenario"))

    def test_manual_priority_can_be_omitted_from_response(self) -> None:
        test_case = TestCaseGenerationStandardTestCase(
            testCaseId="TC-AED-10-001",
            title="Verify successful login",
            type="Positive",
            preconditions=["User account exists"],
            steps=["Navigate to login page", "Enter valid email", "Click login button"],
            expectedResult="User is redirected to dashboard",
            tags=["authentication"],
        )

        self.assertIsNone(test_case.priority)
