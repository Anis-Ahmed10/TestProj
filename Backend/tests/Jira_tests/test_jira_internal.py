import unittest

from app.services.internal import (
    build_description,
    build_row_signature,
    build_test_case_signature,
    normalize_text,
)


class DummyRequest:
    test_cases = [1, 2]


class HelperFullCoverageTests(unittest.TestCase):

    def test_normalize_text_list(self):
        result = normalize_text(["Hello", "World"])
        self.assertEqual(result, "hello world")

    def test_normalize_text_string(self):
        result = normalize_text("  HELLO   WORLD ")
        self.assertEqual(result, "hello world")

    def test_build_test_case_signature_standard(self):
        test_case = {
            "steps": "Click login",
            "expected": "Login success",
        }

        result = build_test_case_signature(test_case)

        self.assertEqual(
            result,
            "click login|login success",
        )

    def test_build_test_case_signature_bdd(self):
        test_case = {
            "scenario": {
                "given": "user exists",
                "when": "user logs in",
                "then": "dashboard shown",
            }
        }

        result = build_test_case_signature(test_case)

        self.assertEqual(
            result,
            ("user exists|" "user logs in|" "dashboard shown"),
        )

    def test_build_test_case_signature_exploratory(self):
        test_case = {
            "charter_mission": "Explore login",
            "charter_scope": "Auth",
            "techniques": "Boundary",
        }

        result = build_test_case_signature(test_case)

        self.assertEqual(
            result,
            "explore login|auth|boundary",
        )

    def test_build_row_signature_standard(self):
        row = {
            "steps": "Open login",
            "expected": "Success",
        }

        result = build_row_signature(row)

        self.assertEqual(
            result,
            "open login|success",
        )

    def test_build_row_signature_bdd(self):
        row = {
            "given_steps": "user exists",
            "when_steps": "login clicked",
            "then_steps": "dashboard visible",
        }

        result = build_row_signature(row)

        self.assertEqual(
            result,
            ("user exists|" "login clicked|" "dashboard visible"),
        )

    def test_build_row_signature_exploratory(self):
        row = {
            "charter_mission": "Explore",
            "charter_scope": "Scope",
            "techniques": "Technique",
        }

        result = build_row_signature(row)

        self.assertEqual(
            result,
            "explore|scope|technique",
        )

    def test_build_description_standard(self):
        result = build_description(
            {
                "steps": "step",
                "expected": "result",
            },
            "standard",
        )

        self.assertEqual(result["type"], "doc")

    def test_build_description_bdd(self):
        result = build_description(
            {
                "scenario": {
                    "given": "given",
                    "when": "when",
                    "then": "then",
                }
            },
            "bdd",
        )

        self.assertEqual(result["type"], "doc")

    def test_build_description_exploratory(self):
        result = build_description(
            {
                "charter_mission": "mission",
                "charter_focus": "focus",
                "charter_scope": "scope",
                "techniques": "techniques",
            },
            "exploratory",
        )

        self.assertEqual(result["type"], "doc")

    def test_build_description_unknown(self):
        result = build_description(
            {},
            "unknown",
        )

        self.assertEqual(result["type"], "doc")


if __name__ == "__main__":
    unittest.main()
