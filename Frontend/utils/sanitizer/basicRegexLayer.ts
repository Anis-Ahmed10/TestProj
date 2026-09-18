import { SanitizationRule } from "../../types/sanitizer_types";
import { compileRule, applyRules, RegexFlag } from "./sanitizer";

const PLACEHOLDERS = {
  jwt: "[REDACTED_JWT]",
  password: "[REDACTED_PASSWORD]",
  api_key: "[REDACTED_API_KEY]",
  access_token: "[REDACTED_ACCESS_TOKEN]",
  secret: "[REDACTED_SECRET]",
  date: "[REDACTED_DATE]",
  email: "[REDACTED_EMAIL]",
  url: "[REDACTED_URL]",
  ip_address: "[REDACTED_IP]",
  phone_number: "[REDACTED_PHONE]",
  client_name: "[REDACTED_CLIENT_NAME]",
};

const DEFAULT_BASIC_REGEX_RULES: SanitizationRule[] = [
  compileRule(
    "jwt",
    String.raw`\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b`,
    PLACEHOLDERS.jwt,
  ),

  compileRule(
    "password",
    String.raw`\b(password|passwd|pwd)\s*[:=]\s*['"]?[^'"\s,;]+`,
    `$1=${PLACEHOLDERS.password}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "api_key",
    String.raw`\b(api[_-]?key|apikey)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{12,}`,
    `$1=${PLACEHOLDERS.api_key}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "access_token",
    String.raw`\b(access[_-]?token|bearer)\s*[:= ]\s*['"]?[A-Za-z0-9._\-]{12,}`,
    `$1=${PLACEHOLDERS.access_token}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "secret",
    String.raw`\b(secret|client[_-]?secret)\s*[:=]\s*['"]?[A-Za-z0-9._\-]{8,}`,
    `$1=${PLACEHOLDERS.secret}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "date",
    String.raw`\b(?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:\d{2}|\d{4})\b`,
    PLACEHOLDERS.date,
  ),

  compileRule(
    "email",
    String.raw`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`,
    PLACEHOLDERS.email,
  ),

  compileRule(
    "phone_number",
    String.raw`(?<![\w/.-])(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?){1,3}\d{4,5}(?![\w/.-])`,
    PLACEHOLDERS.phone_number,
  ),

  compileRule(
    "ip_address",
    String.raw`\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b`,
    PLACEHOLDERS.ip_address,
  ),

  compileRule(
    "credit_card",
    String.raw`(?<!\d)(?:\d[ -]*?){13,19}(?!\d)`,
    "[REDACTED_CARD]",
  ),

  compileRule("url", String.raw`\bhttps?://[^\s,;)]+`, PLACEHOLDERS.url),

  compileRule(
    "client_name",
    String.raw`\b(client[_ -]?name|company|customer)\s*[:=]\s*['"]?[A-Za-z0-9 .&_-]{2,}`,
    `$1=${PLACEHOLDERS.client_name}`,
    RegexFlag.GlobalIgnoreCase,
  ),
];

export const DEFAULT_DOCUMENT_REGEX_RULES: SanitizationRule[] = [
  compileRule(
    "jwt",
    String.raw`\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b`,
    PLACEHOLDERS.jwt,
  ),

  compileRule(
    "password",
    String.raw`\b(password|passwd|pwd)\s*[:=]\s*['"]?[^'"\s,;]+`,
    `$1=${PLACEHOLDERS.password}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "api_key",
    String.raw`\b(api[_-]?key|apikey)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{12,}`,
    `$1=${PLACEHOLDERS.api_key}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "access_token",
    String.raw`\b(access[_-]?token|bearer)\s*[:= ]\s*['"]?[A-Za-z0-9._\-]{12,}`,
    `$1=${PLACEHOLDERS.access_token}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "secret",
    String.raw`\b(secret|client[_-]?secret)\s*[:=]\s*['"]?[A-Za-z0-9._\-]{8,}`,
    `$1=${PLACEHOLDERS.secret}`,
    RegexFlag.GlobalIgnoreCase,
  ),

  compileRule(
    "email",
    String.raw`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`,
    PLACEHOLDERS.email,
  ),

  compileRule(
    "phone_number",
    String.raw`(?<![\w/.-])(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?){1,3}\d{4,5}(?![\w/.-])`,
    PLACEHOLDERS.phone_number,
  ),

  compileRule(
    "ip_address",
    String.raw`\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b`,
    PLACEHOLDERS.ip_address,
  ),

  compileRule(
    "credit_card",
    String.raw`(?<!\d)(?:\d[ -]*?){13,19}(?!\d)`,
    "[REDACTED_CARD]",
  ),
];

export function createDocumentRegexLayer(
  rules: SanitizationRule[] = DEFAULT_DOCUMENT_REGEX_RULES,
) {
  return {
    rules,
    sanitizeText(value: string): string {
      return applyRules(value, rules);
    },
  };
}

export function createBasicRegexLayer(
  rules: SanitizationRule[] = DEFAULT_BASIC_REGEX_RULES,
) {
  return {
    rules,
    sanitizeText(value: string): string {
      return applyRules(value, rules);
    },
  };
}
