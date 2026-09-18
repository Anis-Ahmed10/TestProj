// --- Raw API Response Types ---------------------------------------------------

export type TestCaseFormatType = "bdd" | "standard" | "custom";

// BDD test_data shape
export interface BddTestData {
  tags?: string[];
  type?: string;
  priority?: string;
  scenario: {
    given: string[];
    when: string[];
    then: string[];
  };
  testData?: Record<string, string>;
  testCaseKey?: string;
  preconditions?: string[];
  expectedResult?: string;
}

// Standard test_data shape
export interface StandardTestData {
  tags?: string[];
  type?: string;
  steps?: string[];
  priority?: string;
  testData?: Record<string, string>;
  testCaseKey?: string;
  preconditions?: string[];
  expectedResult?: string;
}

// Custom test_data shape — flexible, only testCaseKey is reliable
export type CustomTestData = Record<string, string>;

// Raw test case from API
export interface RawTestCase {
  id: string;
  title: string;
  test_format_type: TestCaseFormatType;
  test_data: Record<string, any>;
  jira_key?: string;
  status?: string;
  created_at: string;
}

// Raw user story from API
export interface RawUserStory {
  id: string;
  story_key: string;
  title: string;
  description?: string;
  acceptance_criteria?: string;
  priority?: string;
  story_edit_logs?: unknown[];
  test_cases: RawTestCase[];
}

// Raw epic from API
export interface RawEpic {
  epic_id: string;
  epic_key: string;
  epic_title: string;
  user_stories: RawUserStory[];
}

// Raw project from API
export interface RawProject {
  project_id: string;
  project_name: string;
  epics: RawEpic[];
}

// Full API response
export interface TestCaseLibraryApiResponse {
  success: boolean;
  message: string;
  data: RawProject[];
}

// --- Flattened / Enriched TestCase (used in UI) -------------------------------

export interface TestCaseLibraryRow {
  // Identity
  id: string;
  tcId: string; // testCaseKey from test_data
  jiraKey: string;
  status: string;
  createdAt: string;

  // Core fields
  title: string;
  test_format_type: TestCaseFormatType;

  // Fields common to bdd & standard (may be absent for custom)
  priority?: string;
  type?: string; // "type" field (Positive/Negative/Edge Case etc.)
  tags?: string[];
  preconditions?: string[];
  expectedResult?: string;
  testData?: Record<string, string>;

  // Standard-specific
  steps?: string[];

  // BDD-specific
  scenario?: {
    given: string[];
    when: string[];
    then: string[];
  };

  // Custom: all dynamic fields except title/id/testCaseKey
  customFields?: Record<string, any>;

  // Hierarchy context
  userStoryId: string;
  storyKey: string;
  storyTitle: string;
  storyDescription?: string;
  storyAcceptanceCriteria?: string;

  epicId: string;
  epicKey: string;
  epicTitle: string;

  projectId: string;
  projectName: string;
}

export type DetailTab = "test-case" | "user-story" | "metadata";
export type FilterValue = "all" | string;
export type ApprovalStatusFilter = "approved" | "unapproved" | "all";
export type FilterState = {
  priority: FilterValue;
  format: FilterValue;
  type: FilterValue;
};

export const TCL_SELECT_THEME = {
  token: {
    colorPrimary: "#1f3333",
    controlOutline: "rgba(31, 51, 51, 0.1)",
    controlItemBgActive: "#eef2f2",
  },
};

export interface BulkTestCaseUpdateResult {
  id: string;
  status: string;
  success: boolean;
  error?: string | null;
}

export interface BulkUpdateTestCaseStatusResponse {
  found_count: number;
  updated_count: number;
  results: BulkTestCaseUpdateResult[];
}

export const TEST_CASE_STATUS = {
  APPROVED: "approved",
  PENDING: "pending",
  ARCHIVED: "archived",
} as const;

export type TestCaseStatus =
  (typeof TEST_CASE_STATUS)[keyof typeof TEST_CASE_STATUS];
