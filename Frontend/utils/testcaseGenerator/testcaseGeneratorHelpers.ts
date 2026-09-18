import {
  ContextDocumentRequest,
  ContextDocumentPayload,
  EpicGroup,
  EpicPayload,
  GenerationSettings,
  TestCase,
  BackendResponse,
  TestGeneratorRequest,
  FlatTestCase,
  TestGeneratorResponseData,
  GenerationIssueCard,
  TEST_CASE_FORMATS,
  TestCaseFormat,
  UserStoryRow,
  StoryStatus,
} from "@/types/testGenerator";

import {
  TestCaseLibraryRow,
  RawProject,
  RawTestCase,
  RawUserStory,
  RawEpic,
} from "@/types/testCaseLibrary";

// ===== Data Normalization Helpers =====
export function toBackendFormat(
  format: GenerationSettings["format"],
): "standard" | "bdd" | "custom" {
  if (format === TEST_CASE_FORMATS.CUSTOM) return "custom";
  return format === TEST_CASE_FORMATS.BDD ? "bdd" : "standard";
}

export function normalizePriority(value: unknown): TestCase["priority"] {
  const normalized = String(value ?? "Medium")
    .trim()
    .toUpperCase();
  if (
    normalized === "HIGH" ||
    normalized === "H" ||
    normalized === "CRITICAL"
  ) {
    return "High";
  }
  if (normalized === "LOW" || normalized === "L") {
    return "Low";
  }
  return "Medium";
}

export function toTextList(value: unknown): string[] {
  if (typeof value === "string") {
    const text = value.trim();
    return text ? [text] : [];
  }
  if (!Array.isArray(value)) return [];
  return value.map((entry) => String(entry).trim()).filter(Boolean);
}

export function buildIssueStoryKeySet(
  generatedData: TestGeneratorResponseData | null,
): Set<string> {
  const storyKeys = new Set<string>();

  generatedData?.generationIssues?.forEach((issue) => {
    issue.traceability?.forEach((traceability) => {
      if (traceability.storyKey) {
        storyKeys.add(traceability.storyKey);
      }
    });

    issue.storyKeys?.forEach((storyKey) => {
      if (storyKey) {
        storyKeys.add(storyKey);
      }
    });
  });

  return storyKeys;
}

export function toScenario(value: unknown): FlatTestCase["scenario"] {
  if (!value || typeof value !== "object") return undefined;
  const scenario = value as Record<string, unknown>;
  const given = toTextList(scenario.given);
  const when = toTextList(scenario.when);
  const then = toTextList(scenario.then);

  if (!given.length && !when.length && !then.length) return undefined;

  return {
    given,
    when,
    then,
  };
}

export function buildIssueCards(
  generatedData: TestGeneratorResponseData | null,
): GenerationIssueCard[] {
  if (!generatedData?.generationIssues?.length) {
    return [];
  }

  const issueCards: GenerationIssueCard[] = [];

  generatedData.generationIssues.forEach((issue, issueIndex) => {
    if (issue.traceability.length > 0) {
      issue.traceability.forEach((traceability, traceIndex) => {
        issueCards.push({
          id: `${issue.code}-${issueIndex}-${traceIndex}`,
          epicKey: traceability.epicKey,
          storyKey: traceability.storyKey,
          code: issue.code,
          message: issue.message,
        });
      });
      return;
    }

    if (issue.storyKeys.length > 0) {
      issue.storyKeys.forEach((storyKey, storyIndex) => {
        issueCards.push({
          id: `${issue.code}-${issueIndex}-${storyIndex}`,
          epicKey: issue.epicKeys[0],
          storyKey,
          code: issue.code,
          message: issue.message,
        });
      });
      return;
    }

    issueCards.push({
      id: `${issue.code}-${issueIndex}`,
      epicKey: issue.epicKeys[0],
      code: issue.code,
      message: issue.message,
    });
  });

  return issueCards;
}

export function getFriendlyBackendErrorMessage(
  response: Response | null,
  payload: BackendResponse | null,
): string {
  if (!response) {
    return "Unable to reach the test case generator backend. Please ensure the backend is running and the URL is correct.";
  }

  const code = payload?.error?.code?.toUpperCase();
  const backendMessage = payload?.error?.message ?? payload?.message;

  const codeMessageMap: Record<string, string> = {
    INVALID_JSON:
      "The request could not be read by the backend. Please retry with valid input.",
    INVALID_INPUT:
      "The user story or generation settings are not valid. Please review the input and try again.",
    NOT_FOUND:
      "The test case generator endpoint could not be found. Please verify the backend URL.",
    HTTP_ERROR: "The backend returned an error while processing the request.",
    AI_AUTH_FAILED:
      "The AI provider authentication failed. Please contact the project owner to verify API credentials.",
    AI_CONNECTION_ERROR:
      "The AI provider is currently unavailable. Please try again later.",
    AI_TIMEOUT: "The AI provider took too long to respond. Please try again.",
    AI_RATE_LIMITED:
      "The AI provider is temporarily rate limited. Please wait a moment and try again.",
    AI_REQUEST_SERIALIZATION_FAILED:
      "Failed to format the request for the AI provider. Please try again.",
    AI_REQUEST_PREPARATION_FAILED:
      "Failed to prepare the request for the AI provider. Please try again.",
    AI_MALFORMED_RESPONSE:
      "The AI provider returned an unexpected response format. Please try again.",
    AI_EMPTY_RESPONSE: "The AI provider returned no content. Please try again.",
    AI_RESPONSE_INVALID:
      "The generated response was not in the expected format. Please review your inputs and try again.",
    AI_PROVIDER_ERROR:
      "The AI provider encountered an error while generating test cases. Please try again.",
    AI_TEST_CASE_INVALID:
      "Some generated test cases were missing required fields. Please review and regenerate.",
    AI_NO_TEST_CASES_GENERATED:
      "No test cases were generated for this story. Please verify the story details and try again.",
    SANITIZATION_FAILED:
      "The request could not be safely processed. Please review your input and try again.",
    PROMPT_ERROR:
      "Failed to load generation templates. Please contact support.",
    INTERNAL_SERVER_ERROR:
      "An unexpected server error occurred while generating test cases. Please try again shortly.",
  };

  if (code && codeMessageMap[code]) {
    return codeMessageMap[code];
  }

  if (response.status === 429) {
    return "The service is rate limited right now. Please wait a little and try again.";
  }
  if (response.status === 500 && code === "TEST_CASES_DB_FAILURE") {
    return "Test cases could not be saved to the database.";
  }

  if (response.status >= 500) {
    return "The backend is currently unable to generate test cases. Please try again shortly.";
  }

  if (response.status === 404) {
    return "The test case generator endpoint was not found. Please verify the backend URL.";
  }

  if (backendMessage) {
    return backendMessage;
  }

  return "Backend rejected the test case generation request.";
}

function normalizeContextDocumentIds(
  contextDocuments: ContextDocumentRequest[],
): ContextDocumentPayload[] {
  return contextDocuments
    .map((document) => ({
      documentId: document.documentId?.trim() || "",
    }))
    .filter((document): document is ContextDocumentPayload =>
      Boolean(document.documentId),
    );
}

function buildSelectedEpics(
  epics: EpicGroup[],
  selectedStoryIds: Set<string>,
): EpicPayload[] {
  return epics
    .map((epic) => ({
      epicId: epic.epicId,
      epicTitle: epic.epicTitle,
      stories: epic.stories
        .filter((story) => selectedStoryIds.has(story.storyId))
        .map((story) => ({
          storyId: story.storyId,
          storyTitle: story.storyTitle,
          description: story.description,
          acceptanceCriteria: story.acceptanceCriteria ?? [],
        })),
    }))
    .filter((epic) => epic.stories.length > 0);
}

export function buildTestGeneratorRequest(args: {
  settings: GenerationSettings;
  epics: EpicGroup[];
  selectedStoryIds: Set<string>;
  contextDocuments: ContextDocumentRequest[];
  impactPrompt: string;
}): TestGeneratorRequest {
  const contextDocuments = normalizeContextDocumentIds(args.contextDocuments);

  if (contextDocuments.length === 0) {
    throw new Error("Attach at least one context document with an id.");
  }

  const epics = buildSelectedEpics(args.epics, args.selectedStoryIds);

  if (epics.length === 0) {
    throw new Error(
      "Select at least one user story before generating test cases.",
    );
  }

  return {
    settings: args.settings,
    contextDocuments,
    impactPrompt: args.impactPrompt.trim(),
    epics,
  };
}

export const downloadExcel = (blob: Blob, fileName: string): void => {
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;

  document.body.appendChild(a);
  a.click();

  setTimeout(() => {
    URL.revokeObjectURL(url);
    a.remove();
  }, 500);
};

export const formatNumberedList = (items?: string[]): string =>
  items?.map((item, index) => `${index + 1}. ${item}`).join("\n") ?? "";

// Represents a single field change on a user story (before/after snapshot).
export interface StoryChange {
  field: "storyTitle" | "description" | "acceptanceCriteria";
  before: string;
  after: string;
}

// Returns the list of field-level differences between the original and current story.
export function computeStoryDiff(
  original: UserStoryRow,
  current: UserStoryRow,
): StoryChange[] {
  const changes: StoryChange[] = [];
  if ((original.storyTitle ?? "") !== (current.storyTitle ?? "")) {
    changes.push({
      field: "storyTitle",
      before: original.storyTitle ?? "",
      after: current.storyTitle ?? "",
    });
  }
  if ((original.description ?? "") !== (current.description ?? "")) {
    changes.push({
      field: "description",
      before: original.description ?? "",
      after: current.description ?? "",
    });
  }
  const beforeAC = (original.acceptanceCriteria ?? []).join("\n");
  const afterAC = (current.acceptanceCriteria ?? []).join("\n");
  if (beforeAC !== afterAC) {
    changes.push({
      field: "acceptanceCriteria",
      before: beforeAC,
      after: afterAC,
    });
  }
  return changes;
}

// Returns the names of required story fields that are empty or missing.
export function getMissingFields(story: {
  storyTitle?: string;
  description?: string;
  acceptanceCriteria?: string[] | string;
}): string[] {
  const missing: string[] = [];
  if (!story.storyTitle?.trim()) missing.push("Title");
  if (!story.description?.trim()) missing.push("Description");
  const ac = Array.isArray(story.acceptanceCriteria)
    ? story.acceptanceCriteria.join("").trim()
    : (story.acceptanceCriteria ?? "").trim();
  if (!ac) missing.push("Acceptance Criteria");
  return missing;
}

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  if (Array.isArray(value)) return value.map(String).join("\n");
  if (typeof value === "object")
    return Object.entries(value)
      .map(([k, v]) => `${k}: ${String(v)}`)
      .join(" | ");
  return String(value);
}

export const buildExportRows = (
  testCases: FlatTestCase[],
  format: TestCaseFormat,
  customFields?: string[],
) => {
  return testCases.map((tc) => {
    const common = {
      Epic_ID: tc.epicId,
      Epic_Title: tc.epicTitle,
      Story_ID: tc.storyId,
      Story_Title: tc.storyTitle,
      Test_Case_ID: tc.testCaseKey ?? tc.id,
      Title: tc.title,
      Type: tc.type ?? "",
      Priority: tc.priority ?? "",
      Preconditions: (tc.preconditions ?? []).join("\n"),
      Tags: (tc.tags ?? []).join(", "),
    };

    if (format === TEST_CASE_FORMATS.CUSTOM) {
      const customRow: Record<string, string> = {
        Epic_ID: tc.epicId,
        Epic_Title: tc.epicTitle,
        Story_ID: tc.storyId,
        Story_Title: tc.storyTitle,
        Test_Case_ID: tc.testCaseKey ?? "",
        // Fixed "Title" column should always come from the test case Title
        Title: tc.title ?? "",
      };

      const customFieldList = customFields ?? [];

      // Helper to map custom field headers -> actual FlatTestCase fields
      const getCustomFieldValue = (fieldName: string): unknown => {
        // Keep explicit mappings for required mismatches between header names and tc keys
        switch (fieldName) {
          case "Test Data":
            return tc.testData;
          case "Expected Result":
            return tc.expectedResult ?? "";
          // These match FlatTestCase property names
          case "Priority":
            return tc.priority ?? "";
          case "Preconditions":
            return tc.preconditions ?? [];
          case "Severity":
            // UI shows a "High/Medium/Low" badge from tc.priority, not a separate severity field
            return tc.priority ?? "";
          case "Type":
            return tc.type ?? "";
          case "Title":
            return tc.title ?? "";
          default:
            break;
        }

        // Attempt dynamic lookup by exact field name, if backend provided those keys in custom format
        return (tc as unknown as Record<string, unknown>)[fieldName];
      };

      // Add custom fields in order, skipping those already represented as fixed columns
      for (const fieldName of customFieldList) {
        if (fieldName === "Title") continue;

        const val = getCustomFieldValue(fieldName);
        // Serialize nested objects/arrays consistently with existing helper
        customRow[fieldName] = formatFieldValue(val);
      }

      return customRow;
    }

    if (format === TEST_CASE_FORMATS.STRUCTURED) {
      return {
        ...common,
        Steps: formatNumberedList(tc.steps),
        Expected_Result: tc.expectedResult ?? "",
      };
    }

    return {
      ...common,
      Given: formatNumberedList(tc.scenario?.given),
      When: formatNumberedList(tc.scenario?.when),
      Then: formatNumberedList(tc.scenario?.then),
    };
  });
};

/** Maps a single raw test case + its context into the UI TestCase shape */
function mapTestCase(
  rawTc: RawTestCase,
  story: RawUserStory,
  epic: RawEpic,
  project: RawProject,
): TestCaseLibraryRow | null {
  const td = rawTc.test_data ?? {};
  const fmt = rawTc.test_format_type;

  const scenario = td.scenario;

  if (
    fmt === "bdd" &&
    (!scenario ||
      ((Array.isArray(scenario.given) ? scenario.given.length : 0) === 0 &&
        (Array.isArray(scenario.when) ? scenario.when.length : 0) === 0 &&
        (Array.isArray(scenario.then) ? scenario.then.length : 0) === 0))
  ) {
    return null;
  }

  if (
    fmt === "standard" &&
    (!Array.isArray(td.steps) ||
      td.expectedResult === null ||
      td.expectedResult === undefined)
  ) {
    return null;
  }

  const base: TestCaseLibraryRow = {
    id: rawTc.id ?? "",
    tcId: String(td.testCaseKey ?? td.testcaseKey ?? ""),
    jiraKey: rawTc.jira_key ?? "",
    status: rawTc.status ?? "",
    createdAt: rawTc.created_at ?? "",
    title: rawTc.title ?? "",
    test_format_type: fmt,

    // Hierarchy
    userStoryId: story.id ?? "",
    storyKey: story.story_key ?? "",
    storyTitle: story.title ?? "",
    storyDescription: story.description ?? "",
    storyAcceptanceCriteria: story.acceptance_criteria ?? "",
    epicId: epic.epic_id ?? "",
    epicKey: epic.epic_key ?? "",
    epicTitle: epic.epic_title ?? "",
    projectId: project.project_id ?? "",
    projectName: project.project_name ?? "",
  };

  if (fmt === "bdd") {
    base.priority = td.priority ?? "";
    base.type = td.type ?? "";
    base.tags = Array.isArray(td.tags) ? td.tags : [];
    base.preconditions = Array.isArray(td.preconditions)
      ? td.preconditions
      : [];
    base.expectedResult = td.expectedResult ?? "";
    base.testData = td.testData ?? {};
    base.scenario = {
      given: Array.isArray(scenario?.given) ? scenario.given : [],
      when: Array.isArray(scenario?.when) ? scenario.when : [],
      then: Array.isArray(scenario?.then) ? scenario.then : [],
    };
  } else if (fmt === "standard") {
    base.priority = td.priority ?? "";
    base.type = td.type ?? "";
    base.tags = Array.isArray(td.tags) ? td.tags : [];
    base.preconditions = Array.isArray(td.preconditions)
      ? td.preconditions
      : [];
    base.expectedResult = td.expectedResult ?? "";
    base.testData = td.testData ?? {};
    base.steps = Array.isArray(td.steps) ? td.steps : [];
  } else {
    // custom — dynamic fields, extract known ones if present, rest go into customFields
    const EXCLUDED_CUSTOM_KEYS = new Set(["testCaseKey", "testcaseKey"]);
    const customFields: Record<string, any> = {};
    for (const [key, value] of Object.entries(td)) {
      if (
        !EXCLUDED_CUSTOM_KEYS.has(key) &&
        value !== null &&
        value !== undefined
      ) {
        customFields[key] = value;
      }
    }
    // Try to pick up priority from custom fields if present
    base.priority = td.Priority ?? td.priority;
    base.type = td.Type ?? td.type;
    base.customFields = customFields;
  }

  return base;
}

/** Converts the nested API structure into a flat enriched TestCase array */
export function flattenTestCases(projects: RawProject[]): TestCaseLibraryRow[] {
  const result: TestCaseLibraryRow[] = [];

  for (const project of projects) {
    for (const epic of project.epics ?? []) {
      for (const story of epic.user_stories ?? []) {
        for (const rawTc of story.test_cases ?? []) {
          const mappedTestCase = mapTestCase(rawTc, story, epic, project);

          if (mappedTestCase) {
            result.push(mappedTestCase);
          }
        }
      }
    }
  }

  return result;
}

export function getStoryDisplayStatus(args: {
  status?: string;
  isApproved?: boolean;
}): StoryStatus {
  const normalizedStatus = args.status?.trim().toLowerCase();

  if (normalizedStatus === "approved") {
    return "Approved";
  }

  // Awaiting a reviewer decision — distinct from a saved-but-never-submitted story.
  if (normalizedStatus === "pending_approval") {
    return "In Review";
  }

  if (args.isApproved) {
    return "Approved";
  }

  if (normalizedStatus === "rejected") {
    return "Rejected";
  }

  return "Pending Review";
}
