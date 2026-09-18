import { apiRequest } from "@/utils/apiRequest/apiRequest";

import {
  TestCaseLibraryRow as TestCase,
  TestCaseLibraryApiResponse,
  BulkUpdateTestCaseStatusResponse,
  TestCaseStatus,
} from "@/types/testCaseLibrary";

import { flattenTestCases } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";

export async function updateTestCaseStatus(
  testCaseIds: string[],
  status: TestCaseStatus,
  projectId?: string,
): Promise<BulkUpdateTestCaseStatusResponse | undefined> {
  const payload = await apiRequest<{
    success: boolean;
    message: string;
    data: BulkUpdateTestCaseStatusResponse;
  }>("/api/v1/test-cases/status", {
    method: "PATCH",
    body: JSON.stringify({
      testCaseIds,
      status,
      ...(projectId ? { projectId } : {}),
    }),
  });

  return payload?.data;
}

export async function fetchTestCasesLibrary(
  projectId: string,
  status?: string,
): Promise<TestCase[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const payload = await apiRequest<TestCaseLibraryApiResponse>(
    `/api/v1/test-cases/library/${projectId}${query}`,
    { method: "GET", cache: "no-store" },
  );

  if (!payload?.success || !Array.isArray(payload.data)) {
    throw new Error("Unexpected response format from test case library API");
  }
  return flattenTestCases(payload.data);
}
