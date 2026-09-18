export type RecommendedAction = "Must Run" | "Should Run" | "Can Skip";
export type Tier = "Smoke" | "Sanity" | "Full";
export type TestType = "Automated" | "Manual";

export interface TestCaseImpactRow {
  id: string; // = testCaseKey, used as React/table key
  testCaseKey: string;
  testCaseName: string;
  confidence: number; // 0–100, from backend
  recommendedAction: RecommendedAction;
  reason: string;
  tier: Tier;
  impactedModules: string[];
  relatedStories: string[];
  testType: TestType;
}

export interface ImpactSummary {
  mustRun: number;
  shouldRun: number;
  canSkip: number;
  confidence: number; // 0–100 average
}

export interface ImpactAnalysisResult {
  summary: ImpactSummary;
  testCases: TestCaseImpactRow[];
  analysisIssues: { message?: string }[];
}

export const STRATEGIES = {
  auto: {
    label: "Auto — let AI decide",
    note: "AI selected Selective. Highest-risk tests selected. Can Skip tests excluded.",
  },
  selective: {
    label: "Selective (Risk-Based)",
    note: "Highest-risk tests selected. Can Skip tests excluded. Should Run tests included where time permits.",
  },
  all: {
    label: "Retest All",
    note: "All tests will run regardless of risk. Every test case is included.",
  },
  prioritised: {
    label: "Prioritised",
    note: "All tests included, ordered by risk score. Work top to bottom and stop when your time runs out.",
  },
} as const;

export type RegressionStrategy = keyof typeof STRATEGIES;
export type ChangeType = "defect" | "feature" | "config" | null;
export type SuiteSource = "internal" | "jira";

export interface ProjectUserStory {
  storyId: string;
  jiraIssueKey?: string | null;
  title: string;
  description: string;
}
