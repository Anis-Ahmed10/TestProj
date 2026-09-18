import {
  ImpactAnalysisResult,
  TestCaseImpactRow,
  RecommendedAction,
  Tier,
  RegressionStrategy,
  ChangeType,
  SuiteSource,
} from "@/types/impactAnalyzer";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

const REGRESSION_ENDPOINT = "/api/v1/regression-analyzer";

export interface AnalyzeImpactParams {
  projectId: string;
  storyKeys: string[];
  changeType: Exclude<ChangeType, null>;
  regressionStrategy: RegressionStrategy;
  suiteSource: SuiteSource;
  impactPrompt?: string;
  contextDocuments?: string[];
  userId?: string;
  signal?: AbortSignal;
}

type BackendTestCase = {
  testCaseKey: string;
  title: string;
  classification: RecommendedAction;
  reason: string;
  tier: Tier;
  confidence: number;
  impactedModules?: string[];
  relatedStories?: string[];
  testType?: "Automated" | "Manual";
};

type BackendData = {
  summary: {
    mustRun: number;
    shouldRun: number;
    canSkip: number;
    confidence: number;
  };
  testCases: BackendTestCase[];
  analysisIssues?: { message?: string }[];
};

type BackendSuccessPayload = {
  data?: BackendData;
};

function regressionAnalyzerError({ response, body }: ApiErrorContext): Error {
  if (!response) {
    return new Error(
      "Regression analyzer backend is not reachable. Make sure the AI service is running and NEXT_PUBLIC_LAMBDA_URL (or NEXT_PUBLIC_BACKEND_API_URL) points to it.",
    );
  }

  const errorShape = body as
    | { error?: { message?: unknown }; detail?: unknown }
    | null
    | undefined;
  const backendMessage = errorShape?.error?.message ?? errorShape?.detail;

  return new Error(
    typeof backendMessage === "string"
      ? backendMessage
      : `Analysis failed (${response.status})`,
  );
}

export async function analyzeImpact(
  params: AnalyzeImpactParams,
): Promise<ImpactAnalysisResult> {
  const {
    projectId,
    storyKeys,
    changeType,
    regressionStrategy,
    suiteSource,
    impactPrompt,
    contextDocuments,
    userId,
    signal,
  } = params;

  const payload = await apiRequest<BackendSuccessPayload>(REGRESSION_ENDPOINT, {
    method: "POST",
    lambda: true,
    body: JSON.stringify({
      projectId,
      source: { storyKeys },
      changeType,
      regressionStrategy,
      suiteSource,
      impactPrompt: impactPrompt || undefined,
      contextDocuments: contextDocuments ?? [],
      userId: suiteSource === "jira" ? userId : undefined,
    }),
    signal,
    mapError: regressionAnalyzerError,
  });

  const data = payload?.data;

  if (!data?.summary || !Array.isArray(data.testCases)) {
    throw new Error(
      "Regression analysis returned an unexpected response. Please try again.",
    );
  }
  if (data.testCases.length === 0) {
    throw new Error("No test cases could be analysed by the AI provider.");
  }

  const testCases: TestCaseImpactRow[] = data.testCases.map((tc, index) => ({
    id: `${tc.testCaseKey}-${index}`,
    testCaseKey: tc.testCaseKey,
    testCaseName: tc.title,
    confidence: tc.confidence,
    recommendedAction: tc.classification,
    reason: tc.reason,
    tier: tc.tier,
    impactedModules: tc.impactedModules ?? [],
    relatedStories: tc.relatedStories ?? [],
    testType: tc.testType === "Automated" ? "Automated" : "Manual",
  }));

  return {
    summary: {
      mustRun: data.summary.mustRun,
      shouldRun: data.summary.shouldRun,
      canSkip: data.summary.canSkip,
      confidence: data.summary.confidence,
    },
    testCases,
    analysisIssues: data.analysisIssues ?? [],
  };
}
