export type AiCooldownServiceName =
  | "test-generator"
  | "regression-analyzer"
  | "automation-selector";

export const AI_COOLDOWN_SERVICE = {
  TEST_GENERATOR: "test-generator",
  REGRESSION_ANALYZER: "regression-analyzer",
  AUTOMATION_SELECTOR: "automation-selector",
} as const satisfies Record<string, AiCooldownServiceName>;

export const AI_COOLDOWN_LOG_SERVICE_NAME = "ai" as const;
