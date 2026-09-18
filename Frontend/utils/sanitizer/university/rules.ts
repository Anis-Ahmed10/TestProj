import { compileRule, RegexFlag } from "../sanitizer";
import { SanitizationRule } from "../../../types/sanitizer_types";
import { PLACEHOLDERS } from "./placeholders";
import { UNIVERSITY_KEYWORDS } from "./keywords";

function escapeRegex(value: string): string {
  return value.replaceAll(/[.*+?^${}()|[\]\\]/g, String.raw`\$&`);
}

function keywordUnion(keywords: string[]): string {
  return keywords
    .map((keyword) => escapeRegex(keyword).replaceAll(/\s+/g, String.raw`\s+`))
    .sort((a, b) => b.length - a.length)
    .join("|");
}

function institutionNamePattern(name: string): string {
  return escapeRegex(name)
    .replaceAll("'", String.raw`['\u2019]?`)
    .replaceAll(",", String.raw`,?\s*`)
    .replaceAll(/\s+/g, String.raw`\s+`);
}

const VALUE_SEPARATOR = String.raw`(\s*(?:\.|:|#|=|-|\bis\b)?\s*)`;
const STRICT_VALUE_SEPARATOR = String.raw`(\s*(?:[:=#-]|\bis\b)\s*)`;
const ID_VALUE = String.raw`(?=[A-Za-z0-9_./-]*\d)[A-Za-z0-9][A-Za-z0-9_./-]{1,24}`;
const REFERENCE_VALUE = String.raw`(?=[A-Za-z0-9$.,_/-]*\d)[A-Za-z0-9$.,_/-]{3,40}`;
const FINANCIAL_VALUE = String.raw`[^.\n;|]{1,80}`;
const SHORT_CODE_VALUE = String.raw`[A-Z0-9][A-Z0-9_-]{0,9}`;
const LOCATION_VALUE = String.raw`(?=[A-Za-z0-9-]*\d)[A-Za-z]?[A-Za-z0-9-]{0,10}`;
const FREE_TEXT_VALUE = String.raw`['"]?[^'"\n.;|]{2,80}`;

function createUniversityRules(): SanitizationRule[] {
  return [
    compileRule(
      "university_name_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.university_field_labels,
      )})\b${VALUE_SEPARATOR}[A-Za-z][A-Za-z0-9 &.'-]{2,80}`,
      `$1$2${PLACEHOLDERS.university_name}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "university_name_direct_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.university_direct_labels,
      )})\b(\s*[:=#-]\s*)[A-Za-z][A-Za-z0-9 &.'-]{2,80}`,
      `$1$2${PLACEHOLDERS.university_name}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "uk_higher_education_exact",
      UNIVERSITY_KEYWORDS.uk_higher_education_names
        .map((name) => String.raw`\b${institutionNamePattern(name)}\b`)
        .sort((a, b) => b.length - a.length)
        .join("|"),
      PLACEHOLDERS.university_name,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "university_name_of",
      String.raw`\b(?:University|College|Institute)\s+of\s+[A-Z][A-Za-z&.'-]*(?:\s+[A-Z][A-Za-z&.'-]*){0,5}\b`,
      PLACEHOLDERS.university_name,
    ),

    compileRule(
      "university_name_acronym",
      String.raw`\b(?:${keywordUnion(
        UNIVERSITY_KEYWORDS.university_acronyms,
      )})\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\b`,
      PLACEHOLDERS.university_name,
    ),

    compileRule(
      "university_short_name",
      String.raw`\b(?:${keywordUnion(
        UNIVERSITY_KEYWORDS.university_acronyms,
      )})\b`,
      PLACEHOLDERS.university_name,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "university_name_suffix",
      String.raw`\b[A-Z][A-Za-z&.'-]*(?:\s+[A-Z][A-Za-z&.'-]*){0,5}\s+(?:University|College|Institute|Polytechnic)\b`,
      PLACEHOLDERS.university_name,
    ),

    compileRule(
      "student_id_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.student_id_labels,
      )})\b${VALUE_SEPARATOR}${ID_VALUE}\b`,
      `$1$2${PLACEHOLDERS.student_id}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "student_id_structured",
      String.raw`\b(?:STU|STD|ENR|REG|ADM)[-_]?\d{4,12}\b`,
      PLACEHOLDERS.student_id,
    ),

    compileRule(
      "employee_id_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.employee_id_labels,
      )})\b${VALUE_SEPARATOR}${ID_VALUE}\b`,
      `$1$2${PLACEHOLDERS.employee_id}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "employee_id_structured",
      String.raw`\b(?:EMP|FAC|STAFF)[-_]?\d{3,10}\b`,
      PLACEHOLDERS.employee_id,
    ),

    compileRule(
      "course_code",
      String.raw`\b(?!(?:STU|STD|ENR|REG|ADM|EMP|FAC|SCH|FEL)[-_]?\d)[A-Z]{2,4}\s?-?\d{3,4}[A-Z]?\b`,
      PLACEHOLDERS.course_code,
    ),

    compileRule(
      "class_section",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.section_labels,
      )})\b${VALUE_SEPARATOR}${SHORT_CODE_VALUE}\b`,
      `$1$2${PLACEHOLDERS.class_section}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "gpa",
      String.raw`\b(gpa|cgpa|sgpa)\b(\s*(?:[:=#-]|\bis\b)?\s*)\d(?:\.\d{1,2})?(?:\s*/\s*\d(?:\.\d{1,2})?)?\b`,
      `$1$2${PLACEHOLDERS.academic_record}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "academic_record_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.academic_record_labels,
      )})\b${STRICT_VALUE_SEPARATOR}${FREE_TEXT_VALUE}`,
      `$1$2${PLACEHOLDERS.academic_record}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "financial_amount_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.financial_info_labels,
      )})\b${STRICT_VALUE_SEPARATOR}${FINANCIAL_VALUE}`,
      `$1$2${PLACEHOLDERS.financial_info}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "financial_info_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.financial_info_labels,
      )})\b${VALUE_SEPARATOR}${REFERENCE_VALUE}\b`,
      `$1$2${PLACEHOLDERS.financial_info}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "financial_info_context",
      String.raw`\b(?:${keywordUnion(
        UNIVERSITY_KEYWORDS.financial_context_terms,
      )})\b(?:\s+[^.\n;]{0,80})?`,
      PLACEHOLDERS.financial_info,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "scholarship_id_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.scholarship_labels,
      )})\b${VALUE_SEPARATOR}${ID_VALUE}\b`,
      `$1$2${PLACEHOLDERS.scholarship_id}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "scholarship_id_structured",
      String.raw`\b(?:SCH|SCHOLARSHIP|GRANT|FEL)[-_]?\d{4,12}\b`,
      PLACEHOLDERS.scholarship_id,
    ),

    compileRule(
      "system_url",
      String.raw`\bhttps?:\/\/[^\s,;)]*(?:\.edu|\.ac\.|\.internal|intranet|portal|lms|erp|sis|blackboard|canvas|moodle)[^\s,;)]*`,
      PLACEHOLDERS.system_url,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "bare_system_url",
      String.raw`\b(?:[A-Za-z0-9-]+\.)+(?:edu|ac\.[A-Za-z]{2}|internal)(?:\/[^\s,;)]*)?`,
      PLACEHOLDERS.system_url,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "internal_system_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.internal_system_labels,
      )})\b${STRICT_VALUE_SEPARATOR}[A-Za-z][A-Za-z0-9 ._-]{2,50}(?:\s*\([^)]*\))?`,
      `$1$2${PLACEHOLDERS.internal_system}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "internal_system_name",
      String.raw`\b(?:${keywordUnion(
        UNIVERSITY_KEYWORDS.internal_system_names,
      )})\b`,
      PLACEHOLDERS.internal_system,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "location_detail_numbered",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.location_labels,
      )})\b(\s*(?:no\.?|number|#|:|=|-)?\s*)${LOCATION_VALUE}\b`,
      `$1$2${PLACEHOLDERS.location_detail}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "location_detail_block",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.location_block_labels,
      )})\b(\s*(?:#|:|=|-)?\s*)[A-Z]\b`,
      `$1$2${PLACEHOLDERS.location_detail}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "room_number",
      String.raw`(\broom\b)(\s*(?:no\.?|number|#|:|=|-)?\s*)\d+\b`,
      `$1$2${PLACEHOLDERS.location_detail}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "research_data_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.research_data_labels,
      )})\b${STRICT_VALUE_SEPARATOR}${FREE_TEXT_VALUE}`,
      `$1$2${PLACEHOLDERS.research_data}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "unpublished_thesis_title",
      String.raw`\bunpublished thesis titled\s*"[^"\n]+"`,
      `unpublished thesis titled ${PLACEHOLDERS.research_data}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "proprietary_dataset_context",
      String.raw`\bproprietary dataset\b(?:\s+[^.;\n]{0,80})?`,
      PLACEHOLDERS.research_data,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "research_data_irb",
      String.raw`\bIRB-\d{4}-\d{2,6}\b`,
      PLACEHOLDERS.research_data,
    ),

    compileRule(
      "sensitive_record_context",
      String.raw`\b(?:disciplinary|medical|counseling|counselling|conduct|health)\s+(?:record|records|sessions?)(?:\s+[^.\n]{0,80})?`,
      PLACEHOLDERS.sensitive_record,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "sensitive_record_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.sensitive_record_labels,
      )})\b${STRICT_VALUE_SEPARATOR}${FREE_TEXT_VALUE}`,
      `$1$2${PLACEHOLDERS.sensitive_record}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "event_participation_labeled",
      String.raw`\b(${keywordUnion(
        UNIVERSITY_KEYWORDS.event_participation_labels,
      )})\b${STRICT_VALUE_SEPARATOR}${FREE_TEXT_VALUE}`,
      `$1$2${PLACEHOLDERS.event_participation}`,
      RegexFlag.GlobalIgnoreCase,
    ),

    compileRule(
      "event_participation_context",
      String.raw`(\b(?:participated in|registered for|represented the institute at)\s+)[^.\n]{3,100}`,
      `$1${PLACEHOLDERS.event_participation}`,
      RegexFlag.GlobalIgnoreCase,
    ),
  ];
}

let universityRules: SanitizationRule[] | null = null;

export function getUniversityRules(): SanitizationRule[] {
  if (universityRules === null) {
    universityRules = createUniversityRules();
  }

  return universityRules;
}
