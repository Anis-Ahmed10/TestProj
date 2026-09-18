import { createDocumentRegexLayer } from "@/utils/sanitizer/basicRegexLayer";
import { createUniversityKeywordsLayer } from "@/utils/sanitizer/university/UniversityKeywordsLayer";

const documentSanitizer = createDocumentRegexLayer();
const universitySanitizer = createUniversityKeywordsLayer();

/**
 * Thin adapter that bridges the document processors to document-appropriate
 * sanitization layers.
 *
 * Sanitizes high-confidence secrets (JWTs, API keys, passwords, bearer tokens,
 * emails, IP addresses) as well as university-specific domain keywords (student/employee IDs,
 * GPA, academic records, university names, internal systems, etc.).
 */
export function sanitizeText(text: string): string {
  if (!text || typeof text !== "string") {
    return text;
  }

  let sanitized = documentSanitizer.sanitizeText(text);
  sanitized = universitySanitizer.sanitizeText(sanitized);

  return sanitized;
}
