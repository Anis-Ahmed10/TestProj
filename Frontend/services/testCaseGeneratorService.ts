import {
  TestGeneratorRequest,
  TestGeneratorResponse,
} from "@/types/testGenerator";
import { getFriendlyBackendErrorMessage } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import type { BackendResponse } from "@/types/testGenerator";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

const TEST_GENERATOR_ENDPOINT = "/api/v1/test-generator";

function testGeneratorError({ response, body }: ApiErrorContext): Error {
  return new Error(
    getFriendlyBackendErrorMessage(response, (body as BackendResponse) ?? null),
  );
}

export async function generateTestCases(
  request: TestGeneratorRequest,
): Promise<TestGeneratorResponse> {
  return apiRequest<TestGeneratorResponse>(TEST_GENERATOR_ENDPOINT, {
    method: "POST",
    body: JSON.stringify(request),
    lambda: true,
    isError: (b) => {
      const p = b as { error?: unknown; success?: unknown } | null;
      return Boolean(p?.error) || p?.success === false;
    },
    mapError: testGeneratorError,
  });
}
