import type { BackendAutomationResponse } from "@/types/automationCandidate";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

const AUTOMATION_SELECTOR_ENDPOINT = "/api/v1/automation-selector";

// Above the Lambda's own 15 minute ceiling: the run scales with test case count,
// so the request must not be cut off before the function itself gives up.
const ANALYSIS_TIMEOUT_MS = 16 * 60 * 1000;

function automationError({ response, body, cause }: ApiErrorContext): Error {
  if (!response) {
    if (cause instanceof Error && cause.name === "TimeoutError") {
      return new Error(
        "The automation analysis is still running after 16 minutes and was stopped. Try again, or analyse a project with fewer approved test cases.",
      );
    }
    return new Error(
      "Automation service is not reachable. Make sure NEXT_PUBLIC_LAMBDA_URL points to the AI service Lambda.",
    );
  }

  const errorShape = body as
    | { error?: { message?: unknown }; detail?: unknown; message?: unknown }
    | null
    | undefined;
  const backendMessage =
    errorShape?.error?.message ?? errorShape?.detail ?? errorShape?.message;

  return new Error(
    typeof backendMessage === "string" && backendMessage
      ? backendMessage
      : `Automation analysis failed (${response.status}). Please try again.`,
  );
}

export async function analyzeAutomationCandidates(
  projectId: string,
  signal?: AbortSignal,
): Promise<BackendAutomationResponse> {
  return apiRequest<BackendAutomationResponse>(AUTOMATION_SELECTOR_ENDPOINT, {
    method: "POST",
    body: JSON.stringify({ projectId }),
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(ANALYSIS_TIMEOUT_MS)])
      : AbortSignal.timeout(ANALYSIS_TIMEOUT_MS),
    lambda: true,
    mapError: automationError,
  });
}
