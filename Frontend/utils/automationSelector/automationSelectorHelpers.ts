import type {
  AutomationMixData,
  AutomationTestCase,
  BackendAutomationCategory,
  CategoryConfig,
  CategoryKey,
} from "@/types/automationCandidate";
import { CATEGORY_PROMPT_DEFAULTS } from "@/app/(protected)/automation-selector/mockData";

const CATEGORY_STYLES: Record<
  string,
  { icon: string; iconColor: string; iconBgClass: string }
> = {
  smoke: {
    icon: "FireOutlined",
    iconColor: "#3182CE",
    iconBgClass: "as-ci-smoke",
  },
  regression: {
    icon: "SyncOutlined",
    iconColor: "#C48A20",
    iconBgClass: "as-ci-regression",
  },
  full_regression: {
    icon: "AppstoreOutlined",
    iconColor: "#7C3AED",
    iconBgClass: "as-ci-fullreg",
  },
};

const DEFAULT_CATEGORY_STYLE = {
  icon: "AppstoreOutlined",
  iconColor: "#6B7280",
  iconBgClass: "as-ci-custom",
};

function toRatio(value: number | undefined): number {
  return Number.isFinite(value) ? (value as number) : 0;
}

function toTestCase(
  recommendation: BackendAutomationCategory["recommendations"][number],
  index: number,
): AutomationTestCase {
  return {
    id: recommendation.test_case_id || `${recommendation.tc_id}#${index}`,
    tcKey: recommendation.tc_id,
    name: recommendation.tc_name,
    classification: recommendation.classification,
    level: recommendation.automationLevel ?? null,
    score: toRatio(recommendation.score),
    confidence: toRatio(recommendation.confidence),
    checked: recommendation.classification === "AUTOMATE",
    factors: recommendation.factorScores ?? {},
    reasoning: recommendation.reasoning ?? [],
    decisionPrompt: recommendation.decisionPrompt ?? null,
    ruleOverride: recommendation.ruleOverride ?? null,
  };
}

function buildMeta(testCases: AutomationTestCase[]): string {
  if (!testCases.length) return "No test cases scored";
  const averageConfidence =
    testCases.reduce((total, tc) => total + tc.confidence, 0) /
    testCases.length;
  return `${
    testCases.length
  } TCs · LLM confidence avg ${averageConfidence.toFixed(2)}`;
}

export function toCategoryConfig(
  category: BackendAutomationCategory,
): CategoryConfig {
  const testCases = category.recommendations.map(toTestCase);
  const style =
    CATEGORY_STYLES[category.categoryCode] ?? DEFAULT_CATEGORY_STYLE;
  const prompts = CATEGORY_PROMPT_DEFAULTS[category.categoryCode];

  return {
    key: category.categoryCode,
    title: category.categoryName,
    ...style,
    meta: buildMeta(testCases),
    basePrompt: prompts?.basePrompt ?? "",
    impactPrompt: "",
    factors: prompts?.factors ?? Object.keys(testCases[0]?.factors ?? {}),
    status: category.status,
    failureReason: category.failureReason ?? null,
    counts: {
      all: testCases.length,
      automate: testCases.filter((tc) => tc.classification === "AUTOMATE")
        .length,
      review: testCases.filter((tc) => tc.classification === "REVIEW").length,
      manual: testCases.filter((tc) => tc.classification === "KEEP_MANUAL")
        .length,
    },
    testCases,
  };
}

export function buildCategoryState(categories: BackendAutomationCategory[]): {
  categories: Record<CategoryKey, CategoryConfig>;
  categoryOrder: CategoryKey[];
} {
  const configs = categories.map(toCategoryConfig);
  return {
    categories: Object.fromEntries(configs.map((c) => [c.key, c])),
    categoryOrder: configs.map((c) => c.key),
  };
}

export function computeAutomationMix(
  testCases: AutomationTestCase[],
): AutomationMixData {
  const total = testCases.filter((tc) => tc.level !== null).length || 1;
  const mix: AutomationMixData = {};

  testCases.forEach((tc) => {
    if (tc.level) {
      if (!mix[tc.level]) mix[tc.level] = { percent: 0, selected: 0 };
      mix[tc.level].selected++;
    }
  });

  Object.keys(mix).forEach((level) => {
    mix[level].percent = Math.round((mix[level].selected / total) * 100);
  });

  return mix;
}

export function getUniqueLevels(testCases: AutomationTestCase[]): string[] {
  const levels = new Set(
    testCases
      .map((tc) => tc.level)
      .filter((level): level is string => level !== null),
  );
  return Array.from(levels).sort();
}

export function filterTestCases(
  testCases: AutomationTestCase[],
  filter: "all" | "automate" | "review" | "manual",
  searchQuery: string,
  levelFilter: string,
): AutomationTestCase[] {
  const q = searchQuery.toLowerCase().trim();

  return testCases.filter((tc) => {
    if (filter === "automate" && tc.classification !== "AUTOMATE") return false;
    if (filter === "review" && tc.classification !== "REVIEW") return false;
    if (filter === "manual" && tc.classification !== "KEEP_MANUAL")
      return false;

    if (levelFilter && levelFilter !== "All Levels") {
      if (tc.level === null && levelFilter !== "—") return false;
      if (tc.level !== null && tc.level !== levelFilter) return false;
    }

    if (
      q &&
      !tc.tcKey.toLowerCase().includes(q) &&
      !tc.name.toLowerCase().includes(q)
    )
      return false;

    return true;
  });
}
