import type { ProcessStatus } from "@/types/testGenerator";

export type AutomationClassification = "AUTOMATE" | "REVIEW" | "KEEP_MANUAL";
export type AutomationLevel = string | null;
export type CategoryStatus = "scored" | "partial" | "error";

export interface AutomationTestCase {
  id: string;
  tcKey: string;
  name: string;
  classification: AutomationClassification;
  level: AutomationLevel;
  score: number;
  confidence: number;
  checked: boolean;
  factors: Record<string, number>;
  reasoning: string[];
  decisionPrompt: string | null;
  ruleOverride: string | null;
}

export type CategoryKey = string;

export interface CategoryCounts {
  all: number;
  automate: number;
  review: number;
  manual: number;
}

export interface CategoryConfig {
  key: CategoryKey;
  title: string;
  icon: string;
  iconColor: string;
  iconBgClass: string;
  meta: string;
  basePrompt: string;
  impactPrompt: string;
  factors: string[];
  status: CategoryStatus;
  failureReason: string | null;
  counts: CategoryCounts;
  testCases: AutomationTestCase[];
}

export interface ClassificationThresholds {
  automate: number;
  review: number;
}

export type AutomationMixData = Record<
  string,
  { percent: number; selected: number }
>;

export interface AutomationSelectorState {
  status: ProcessStatus;
  projectId: string | null;
  categories: Record<CategoryKey, CategoryConfig>;
  categoryOrder: CategoryKey[];
  activeCategory: CategoryKey;
  selectedFilter: "all" | "automate" | "review" | "manual";
  searchQuery: string;
  levelFilter: string;
  settingsPanelOpen: boolean;
  settingsActiveTab: CategoryKey;
  thresholds: ClassificationThresholds;
  projectContext: string;
  lastRunTimestamp: string | null;
  rerunning: boolean;
  error: string | null;
  hasRun: boolean;
}

export interface BackendCategoryRecommendation {
  tc_id: string;
  tc_name: string;
  test_case_id: string;
  classification: AutomationClassification;
  automationLevel?: string | null;
  confidence: number;
  score: number;
  factorScores: Record<string, number>;
  reasoning: string[];
  decisionPrompt?: string | null;
  ruleOverride?: string | null;
}

export interface BackendAutomationCategory {
  categoryCode: string;
  categoryName: string;
  status: CategoryStatus;
  recommendations: BackendCategoryRecommendation[];
  failureCode?: string | null;
  failureReason?: string | null;
}

export interface BackendAutomationResponse {
  success: boolean;
  message: string;
  data: { categories: BackendAutomationCategory[] };
}
