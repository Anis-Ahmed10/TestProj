"""Tests for the automation selector API endpoint (currently a retained stub).

The route deliberately returns an empty analysis while the frontend calls the
Lambda directly; these tests pin that stub contract so a regression is visible
when the real service flow is re-enabled.
"""

from __future__ import annotations

import unittest

from app.api.v1.endpoints.automation_selector import analyze_automation_candidates
from app.schemas.automation_selector import AutomationAnalysisRequest
from app.schemas.common import SuccessResponse


class AutomationSelectorEndpointTests(unittest.IsolatedAsyncioTestCase):
    """Verify the stub route shape and payload handling."""

    async def test_returns_standard_success_response(self) -> None:
        payload = AutomationAnalysisRequest(test_cases=[{"title": "Verify login regression"}])

        response = await analyze_automation_candidates(payload)

        self.assertIsInstance(response, SuccessResponse)
        self.assertEqual(response.message, "Automation analysis completed")
        self.assertEqual(response.data, [])


if __name__ == "__main__":
    unittest.main()
