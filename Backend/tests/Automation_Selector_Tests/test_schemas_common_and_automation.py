"""Comprehensive tests for common.py and automation_selector.py schemas."""

import unittest

from pydantic import ValidationError

from app.schemas.automation_selector import (
    AutomationAnalysisData,
    AutomationAnalysisRequest,
    AutomationRecommendation,
    AutomationRecommendationValue,
)
from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    FlexibleModel,
    HealthData,
    SuccessResponse,
)


class HealthDataTests(unittest.TestCase):
    """Test HealthData schema."""

    def test_creates_valid_health_data(self) -> None:
        health = HealthData(status="healthy", service="TestService")
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.service, "TestService")

    def test_health_data_serializes_to_dict(self) -> None:
        health = HealthData(status="ok", service="MyService")
        data = health.model_dump()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "MyService")

    def test_health_data_requires_status(self) -> None:
        with self.assertRaises(ValidationError):
            HealthData(service="TestService")

    def test_health_data_requires_service(self) -> None:
        with self.assertRaises(ValidationError):
            HealthData(status="healthy")


class SuccessResponseTests(unittest.TestCase):
    """Test SuccessResponse schema."""

    def test_creates_success_response_with_data(self) -> None:
        data = {"user_id": 123, "name": "John"}
        response = SuccessResponse(message="User created", data=data)
        self.assertTrue(response.success)
        self.assertEqual(response.message, "User created")
        self.assertEqual(response.data, data)

    def test_success_field_defaults_to_true(self) -> None:
        response = SuccessResponse(message="OK", data={})
        self.assertTrue(response.success)

    def test_success_response_serializes_correctly(self) -> None:
        response = SuccessResponse(message="Test", data={"key": "value"})
        data = response.model_dump()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Test")
        self.assertEqual(data["data"]["key"], "value")

    def test_success_response_with_complex_data(self) -> None:
        complex_data = {
            "items": [1, 2, 3],
            "nested": {"level1": {"level2": "value"}},
        }
        response = SuccessResponse(message="Complex", data=complex_data)
        self.assertEqual(response.data["nested"]["level1"]["level2"], "value")

    def test_success_response_requires_message(self) -> None:
        with self.assertRaises(ValidationError):
            SuccessResponse(data={})

    def test_success_response_requires_data(self) -> None:
        with self.assertRaises(ValidationError):
            SuccessResponse(message="Missing data")


class ErrorDetailTests(unittest.TestCase):
    """Test ErrorDetail schema."""

    def test_creates_error_detail(self) -> None:
        error = ErrorDetail(code="USER_NOT_FOUND", message="The user does not exist")
        self.assertEqual(error.code, "USER_NOT_FOUND")
        self.assertEqual(error.message, "The user does not exist")

    def test_error_detail_serializes_to_dict(self) -> None:
        error = ErrorDetail(code="INVALID_INPUT", message="Field x is required")
        data = error.model_dump()
        self.assertEqual(data["code"], "INVALID_INPUT")
        self.assertEqual(data["message"], "Field x is required")

    def test_error_detail_requires_code(self) -> None:
        with self.assertRaises(ValidationError):
            ErrorDetail(message="Error message")

    def test_error_detail_requires_message(self) -> None:
        with self.assertRaises(ValidationError):
            ErrorDetail(code="ERROR_CODE")


class ErrorResponseTests(unittest.TestCase):
    """Test ErrorResponse schema."""

    def test_creates_error_response(self) -> None:
        error_detail = ErrorDetail(code="SERVER_ERROR", message="Something went wrong")
        response = ErrorResponse(error=error_detail)
        self.assertFalse(response.success)
        self.assertEqual(response.error.code, "SERVER_ERROR")
        self.assertEqual(response.error.message, "Something went wrong")

    def test_error_response_success_field_is_false(self) -> None:
        error = ErrorDetail(code="NOT_FOUND", message="Resource not found")
        response = ErrorResponse(error=error)
        self.assertFalse(response.success)

    def test_error_response_serializes_correctly(self) -> None:
        error = ErrorDetail(code="AUTH_FAILED", message="Invalid credentials")
        response = ErrorResponse(error=error)
        data = response.model_dump()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "AUTH_FAILED")
        self.assertEqual(data["error"]["message"], "Invalid credentials")

    def test_error_response_requires_error(self) -> None:
        with self.assertRaises(ValidationError):
            ErrorResponse()


class FlexibleModelTests(unittest.TestCase):
    """Test FlexibleModel schema."""

    def test_flexible_model_allows_extra_fields(self) -> None:
        model = FlexibleModel(custom_field="value", another="field")
        self.assertEqual(model.custom_field, "value")
        self.assertEqual(model.another, "field")

    def test_flexible_model_serializes_extra_fields(self) -> None:
        model = FlexibleModel(provider_specific="data", config="value")
        data = model.model_dump()
        self.assertEqual(data["provider_specific"], "data")
        self.assertEqual(data["config"], "value")

    def test_flexible_model_with_various_data_types(self) -> None:
        model = FlexibleModel(
            string_val="test",
            int_val=42,
            float_val=3.14,
            list_val=[1, 2, 3],
            dict_val={"nested": "value"},
        )
        data = model.model_dump()
        self.assertEqual(data["string_val"], "test")
        self.assertEqual(data["int_val"], 42)
        self.assertEqual(data["float_val"], 3.14)
        self.assertEqual(data["list_val"], [1, 2, 3])
        self.assertEqual(data["dict_val"]["nested"], "value")

    def test_flexible_model_with_no_fields(self) -> None:
        model = FlexibleModel()
        data = model.model_dump()
        self.assertEqual(data, {})


class AutomationRecommendationValueTests(unittest.TestCase):
    """Test AutomationRecommendationValue enum."""

    def test_automate_value(self) -> None:
        value = AutomationRecommendationValue.automate
        self.assertEqual(value, "AUTOMATE")

    def test_manual_value(self) -> None:
        value = AutomationRecommendationValue.manual
        self.assertEqual(value, "MANUAL")

    def test_enum_has_two_members(self) -> None:
        members = list(AutomationRecommendationValue)
        self.assertEqual(len(members), 2)

    def test_enum_from_string(self) -> None:
        value = AutomationRecommendationValue("AUTOMATE")
        self.assertEqual(value, AutomationRecommendationValue.automate)


class AutomationAnalysisRequestValidationTests(unittest.TestCase):
    """Test AutomationAnalysisRequest validation."""

    def test_accepts_valid_test_cases(self) -> None:
        request = AutomationAnalysisRequest(test_cases=[{"name": "test1"}, {"name": "test2"}])
        self.assertEqual(len(request.test_cases), 2)

    def test_rejects_empty_test_cases_list(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[])
        self.assertIn("at least 1 item", str(context.exception))

    def test_rejects_test_cases_exceeding_max_length(self) -> None:
        test_cases = [{"id": i} for i in range(201)]
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=test_cases)
        self.assertIn("at most 200 items", str(context.exception))

    def test_rejects_empty_test_case_object(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[{}])
        self.assertIn("test_cases cannot contain empty objects", str(context.exception))

    def test_rejects_non_serializable_test_case(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[{"value": object()}])
        self.assertIn("test_cases must be JSON serializable", str(context.exception))

    def test_rejects_non_serializable_nested_value(self) -> None:
        class CustomClass:
            pass

        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[{"nested": {"obj": CustomClass()}}])
        self.assertIn("test_cases must be JSON serializable", str(context.exception))

    def test_accepts_complex_json_serializable_test_cases(self) -> None:
        request = AutomationAnalysisRequest(
            test_cases=[
                {
                    "name": "complex_test",
                    "inputs": [1, 2, 3],
                    "config": {"nested": {"value": "test"}},
                    "metadata": {"author": "John"},
                }
            ]
        )
        self.assertEqual(len(request.test_cases), 1)
        self.assertEqual(request.test_cases[0]["name"], "complex_test")

    def test_accepts_single_test_case(self) -> None:
        request = AutomationAnalysisRequest(test_cases=[{"single": "case"}])
        self.assertEqual(len(request.test_cases), 1)

    def test_accepts_exactly_200_test_cases(self) -> None:
        test_cases = [{"id": i, "name": f"test_{i}"} for i in range(200)]
        request = AutomationAnalysisRequest(test_cases=test_cases)
        self.assertEqual(len(request.test_cases), 200)

    def test_rejects_with_unicode_in_non_serializable(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[{"test": set([1, 2, 3])}])
        self.assertIn("test_cases must be JSON serializable", str(context.exception))

    def test_rejects_multiple_empty_objects(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationAnalysisRequest(test_cases=[{}, {}, {"valid": "test"}])
        self.assertIn("test_cases cannot contain empty objects", str(context.exception))


class AutomationRecommendationTests(unittest.TestCase):
    """Test AutomationRecommendation schema."""

    def test_creates_valid_recommendation(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="test_login",
            recommendation=AutomationRecommendationValue.automate,
            confidence=0.95,
            reasoning=["Deterministic", "No external dependencies"],
        )
        self.assertEqual(rec.test_case_name, "test_login")
        self.assertEqual(rec.recommendation, AutomationRecommendationValue.automate)
        self.assertEqual(rec.confidence, 0.95)
        self.assertEqual(len(rec.reasoning), 2)

    def test_test_case_name_required(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationRecommendation(
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.9,
                reasoning=["reason"],
            )

    def test_test_case_name_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationRecommendation(
                test_case_name="",
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.9,
                reasoning=["reason"],
            )
        self.assertIn("at least 1 character", str(context.exception))

    def test_recommendation_field_required(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationRecommendation(
                test_case_name="test",
                confidence=0.9,
                reasoning=["reason"],
            )

    def test_confidence_must_be_between_0_and_1(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationRecommendation(
                test_case_name="test",
                recommendation=AutomationRecommendationValue.automate,
                confidence=1.5,
                reasoning=["reason"],
            )

    def test_confidence_cannot_be_negative(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationRecommendation(
                test_case_name="test",
                recommendation=AutomationRecommendationValue.automate,
                confidence=-0.1,
                reasoning=["reason"],
            )

    def test_confidence_zero_allowed(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="test",
            recommendation=AutomationRecommendationValue.manual,
            confidence=0.0,
            reasoning=["reason"],
        )
        self.assertEqual(rec.confidence, 0.0)

    def test_confidence_one_allowed(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="test",
            recommendation=AutomationRecommendationValue.automate,
            confidence=1.0,
            reasoning=["reason"],
        )
        self.assertEqual(rec.confidence, 1.0)

    def test_reasoning_required(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationRecommendation(
                test_case_name="test",
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.9,
            )

    def test_reasoning_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError) as context:
            AutomationRecommendation(
                test_case_name="test",
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.9,
                reasoning=[],
            )
        self.assertIn("at least 1 item", str(context.exception))

    def test_manual_recommendation_with_reasons(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="manual_test",
            recommendation=AutomationRecommendationValue.manual,
            confidence=0.3,
            reasoning=[
                "Requires user interaction",
                "Non-deterministic timing",
            ],
        )
        self.assertEqual(rec.recommendation, AutomationRecommendationValue.manual)
        self.assertEqual(len(rec.reasoning), 2)

    def test_allows_extra_fields(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="test",
            recommendation=AutomationRecommendationValue.automate,
            confidence=0.8,
            reasoning=["reason"],
            provider_metadata={"key": "value"},
            custom_field="custom",
        )
        self.assertEqual(rec.provider_metadata, {"key": "value"})
        self.assertEqual(rec.custom_field, "custom")

    def test_serializes_with_extra_fields(self) -> None:
        rec = AutomationRecommendation(
            test_case_name="test",
            recommendation=AutomationRecommendationValue.automate,
            confidence=0.8,
            reasoning=["reason"],
            extra_info={"note": "test"},
        )
        data = rec.model_dump()
        self.assertEqual(data["extra_info"]["note"], "test")


class AutomationAnalysisDataTests(unittest.TestCase):
    """Test AutomationAnalysisData schema."""

    def test_creates_analysis_data_with_recommendations(self) -> None:
        recommendations = [
            AutomationRecommendation(
                test_case_name="test1",
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.9,
                reasoning=["reason1"],
            ),
            AutomationRecommendation(
                test_case_name="test2",
                recommendation=AutomationRecommendationValue.manual,
                confidence=0.4,
                reasoning=["reason2"],
            ),
        ]
        data = AutomationAnalysisData(recommendations=recommendations)
        self.assertEqual(len(data.recommendations), 2)
        self.assertEqual(data.recommendations[0].test_case_name, "test1")

    def test_recommendations_required(self) -> None:
        with self.assertRaises(ValidationError):
            AutomationAnalysisData()

    def test_serializes_recommendations(self) -> None:
        recommendations = [
            AutomationRecommendation(
                test_case_name="test",
                recommendation=AutomationRecommendationValue.automate,
                confidence=0.85,
                reasoning=["reason"],
            )
        ]
        data = AutomationAnalysisData(recommendations=recommendations)
        serialized = data.model_dump()
        self.assertEqual(len(serialized["recommendations"]), 1)
        self.assertEqual(serialized["recommendations"][0]["test_case_name"], "test")

    def test_multiple_recommendations(self) -> None:
        recommendations = [
            AutomationRecommendation(
                test_case_name=f"test_{i}",
                recommendation=(
                    AutomationRecommendationValue.automate
                    if i % 2 == 0
                    else AutomationRecommendationValue.manual
                ),
                confidence=0.5 + (i * 0.1),
                reasoning=[f"reason_{i}"],
            )
            for i in range(5)
        ]
        data = AutomationAnalysisData(recommendations=recommendations)
        self.assertEqual(len(data.recommendations), 5)


if __name__ == "__main__":
    unittest.main()
