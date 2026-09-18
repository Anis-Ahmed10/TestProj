import { applyRules } from "../sanitizer";
import { SanitizationRule } from "../../../types/sanitizer_types";
import { getUniversityRules } from "./rules";

export function createUniversityKeywordsLayer(
  rules: SanitizationRule[] = getUniversityRules(),
) {
  return {
    rules,
    sanitizeText(value: string): string {
      return applyRules(value, rules);
    },
  };
}
