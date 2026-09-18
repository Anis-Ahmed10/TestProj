export const CATEGORY_PROMPT_DEFAULTS: Record<
  string,
  { basePrompt: string; factors: string[] }
> = {
  smoke: {
    basePrompt:
      "You are an expert test automation engineer. Evaluate each test case for suitability as a Smoke test automation candidate. Focus on: execution frequency, feature stability, determinism, critical path coverage, and setup simplicity.\n\nReturn a JSON object matching the exact schema provided.",
    factors: [
      "execution_frequency",
      "feature_stability",
      "determinism",
      "critical_path_coverage",
      "setup_simplicity",
    ],
  },
  regression: {
    basePrompt:
      "You are an expert test automation engineer. Evaluate each test case for suitability as a Regression test automation candidate. Focus on: execution frequency, feature stability, data-driven potential, business criticality, and ROI vs manual effort.\n\nReturn a JSON object matching the exact schema provided.",
    factors: [
      "execution_frequency",
      "feature_stability",
      "data_driven_potential",
      "business_criticality",
      "roi_vs_manual_effort",
    ],
  },
  full_regression: {
    basePrompt:
      "You are an expert test automation engineer. Evaluate each test case for suitability as a Full Regression test automation candidate. Focus on: reuse value, feature stability, execution frequency, automation feasibility, and maintenance cost ratio.\n\nReturn a JSON object matching the exact schema provided.",
    factors: [
      "reuse_value",
      "feature_stability",
      "execution_frequency",
      "automation_feasibility",
      "maintenance_cost_ratio",
    ],
  },
};

export const PROMPT_VARIABLES: Record<string, string[]> = {
  default: [
    "{test_cases}",
    "{project_context}",
    "{execution_time_history}",
    "{impact_prompt}",
  ],
  full_regression: [
    "{test_cases}",
    "{project_context}",
    "{execution_time_history}",
    "{impact_prompt}",
    "{ra_classification_context}",
  ],
};
