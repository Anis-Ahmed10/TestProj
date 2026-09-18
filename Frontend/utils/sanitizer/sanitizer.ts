import { SanitizationRule } from "../../types/sanitizer_types";

class SanitizationError extends Error {
  readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "SanitizationError";
    this.cause = cause;
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Unknown sanitization error";
}

export enum RegexFlag {
  Global = "g",
  IgnoreCase = "i",
  GlobalIgnoreCase = "gi",
}

export function compileRule(
  name: string,
  pattern: string,
  replacement: string,
  flags: string | RegexFlag = RegexFlag.Global,
): SanitizationRule {
  try {
    return {
      name,
      pattern: new RegExp(pattern, flags),
      replacement,
    };
  } catch (error) {
    throw new SanitizationError(
      `Failed to compile sanitization rule "${name}": ${getErrorMessage(
        error,
      )}`,
      error,
    );
  }
}

export function applyRules(value: string, rules: SanitizationRule[]): string {
  let sanitized = value;

  for (const rule of rules) {
    try {
      sanitized = sanitized.replace(rule.pattern, rule.replacement);
    } catch (error) {
      throw new SanitizationError(
        `Failed to apply sanitization rule "${rule.name}": ${getErrorMessage(
          error,
        )}`,
        error,
      );
    }
  }

  return sanitized;
}

export function withSanitizationErrorContext<T>(
  operation: string,
  action: () => T,
): T {
  try {
    return action();
  } catch (error) {
    if (error instanceof SanitizationError) {
      throw error;
    }

    throw new SanitizationError(
      `Failed to ${operation}: ${getErrorMessage(error)}`,
      error,
    );
  }
}
