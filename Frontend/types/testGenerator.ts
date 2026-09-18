export type TestCaseScenario = {
  given?: string[];
  when?: string[];
  then?: string[];
};

export interface TestCase {
  id: string;
  title: string;
  type?: string;
  userStoryId?: string;
  preconditions?: string[];
  steps?: string[];
  expected?: string;
  expectedResult?: string;
  scenario?: TestCaseScenario;
  testData?: Record<string, unknown>;
  tags?: string[];
  techniques?: string[];
  priority?: Priority;
  testCaseKey?: string;
}

export interface FlatTestCase extends TestCase {
  epicId: string;
  epicTitle: string;
  storyId: string;
  storyTitle: string;
}

export type TestCaseFormat =
  | "Structured (ID, Steps, Expected)"
  | "BDD (Given/When/Then)"
  | "Custom (User-defined template)";

export const TEST_CASE_FORMATS = {
  STRUCTURED: "Structured (ID, Steps, Expected)",
  BDD: "BDD (Given/When/Then)",
  CUSTOM: "Custom (User-defined template)",
} as const;

export type TestCaseStatus = "pending" | "approved" | "archived";

export type CoverageDepth =
  | "Standard (Happy + Negative)"
  | "Comprehensive (All paths)"
  | "Smoke (Happy path only)";

export type PriorityAssignment = "Auto-assign by risk" | "All high" | "Manual";

export type CustomStdField =
  | "title"
  | "preconditions"
  | "test_data"
  | "priority"
  | "type"
  | "tags"
  | "severity"
  | "expected_result"
  | "steps";

export type CustomColumn = {
  id: string;
  name: string;
  description: string;
};

export type StandardFieldOption = {
  value: CustomStdField;
  label: string;
  description: string;
};

export const MANDATORY_TITLE = {
  value: "title",
  label: "Title",
  description: "Title field for generated test cases. (Mandatory)",
} as const;

export const standardFieldOptions: StandardFieldOption[] = [
  {
    value: "steps",
    label: "Steps",
    description:
      "Detailed sequence of actions that must be performed to execute the test case and validate the expected behavior.",
  },
  {
    value: "expected_result",
    label: "Expected Result",
    description:
      "Expected application behavior or outcome when the test is executed successfully.",
  },
  {
    value: "preconditions",
    label: "Preconditions",
    description:
      "Required setup, system state, permissions, or dependencies that must exist before executing the test case.",
  },
  {
    value: "test_data",
    label: "Test Data",
    description:
      "Input values, sample records, credentials, or datasets required for test execution.",
  },
  {
    value: "priority",
    label: "Priority",
    description:
      "Business or risk-based importance of the test case (High, Medium, Low).",
  },
  {
    value: "severity",
    label: "Severity",
    description:
      "Impact on the application if the tested functionality fails (Critical, Major, Minor).",
  },
  {
    value: "type",
    label: "Type",
    description:
      "Test classification such as Functional, Regression, Integration, Smoke, Sanity, or UAT.",
  },
  {
    value: "tags",
    label: "Tags",
    description:
      "Labels used for categorization, filtering, reporting, and test suite organization.",
  },
];

export const allStandardFieldOptions = [
  {
    value: MANDATORY_TITLE.value,
    label: MANDATORY_TITLE.label,
    description: MANDATORY_TITLE.description,
  },
  ...standardFieldOptions,
];

export type CustomTableRow = {
  id: string;
  name: string;
  description: string;
  isCustom: boolean;
};

export type StandardFieldSelectOption = {
  value: CustomStdField;
  label: string;
  description: string;
  disabled?: boolean;
};

export interface GenerationSettings {
  format: TestCaseFormat;
  coverage: CoverageDepth;
  priority: PriorityAssignment;
  customFields?: Array<{ name: string; description: string }>;
}

export type WorkflowStep = "upload" | "review" | "approved" | "generated";
// ===== Backend / Helper Types moved from utils =====
export type BackendTestCase = Record<string, unknown>;

export type BackendResponse = {
  success?: boolean;
  message?: string;
  error?: {
    code?: string;
    message?: string;
  };
  data?: {
    test_cases?: BackendTestCase[];
  };
};

export type StoryGroup = {
  id: string;
  epicId?: string;
  title: string;
  description: string;
  acceptance_criteria: string[];
  test_cases: TestCase[];
};

export type StoryStatus =
  | "Approved"
  | "Pending Review"
  | "Rejected"
  | "Already Approved"
  // Sent for approval, awaiting a reviewer decision.
  | "In Review";
export type Priority = "High" | "Medium" | "Low";

export interface UserStoryRow {
  storyId: string;
  epicId: string;
  storyTitle: string;
  description: string;
  priority: Priority;
  acceptanceCriteria: string[];
  status?: string;
  alreadyExists?: boolean;
}

export interface EpicGroup {
  epicId: string;
  epicTitle: string;
  stories: UserStoryRow[];
}

export interface ExcelRow {
  Epic_ID: string;
  Epic_Title: string;
  Story_ID: string;
  Story_Title: string;
  Description: string;
  Priority: Priority;
  Acceptance_Criteria: string;
}

// Request types for backend test-generator
export interface ContextDocumentRequest {
  documentId: string;
  title: string;
  link?: string;
  content?: string;
  s3Key?: string;
  fileName: string;
}

export interface ContextDocumentPayload {
  documentId: string;
}

export interface EpicPayload {
  epicId: string;
  epicTitle: string;
  stories: Array<{
    storyId: string;
    storyTitle: string;
    description: string;
    acceptanceCriteria: string[];
  }>;
}

export interface TestGeneratorRequest {
  settings: GenerationSettings;
  contextDocuments: ContextDocumentPayload[];
  impactPrompt: string;
  epics: EpicPayload[];
}

export interface TestCaseGenerationMetadata {
  generatedAt: string;
  format: string;
  coverage: string;
  priorityMode: string;
  customFields?: string[];
  totalEpics: number;
  totalStories: number;
  totalTestCases: number;
}

export interface TestCaseGenerationIssue {
  storyKeys: string[];
  epicKeys: string[];
  traceability: Array<{
    epicKey: string;
    storyKey: string;
  }>;
  code: string;
  message: string;
}

export interface TestGeneratorGeneratedTestCase {
  testCaseId: string;
  testCaseKey?: string;
  title: string;
  type: string;
  priority: string;
  preconditions: string[];
  testData?: Record<string, unknown>;
  expectedResult?: string;
  tags?: string[];
  steps?: string[];
  scenario?: Record<string, unknown>;
}

export interface TestGeneratorStoryGroup {
  storyKey: string;
  storySummary: string;
  testCases: TestGeneratorGeneratedTestCase[];
}

export interface TestGeneratorEpicGroup {
  epicKey: string;
  epicSummary: string;
  stories: TestGeneratorStoryGroup[];
}

export interface TestGeneratorResponseData {
  metadata: TestCaseGenerationMetadata;
  generatedTestCases: TestGeneratorEpicGroup[];
  generationIssues: TestCaseGenerationIssue[];
}

export type GenerationIssueCard = {
  id: string;
  epicKey?: string;
  storyKey?: string;
  code: string;
  message: string;
};

export type ValidationState = {
  issueCards: GenerationIssueCard[];
  blockedStoryKeys: Set<string>;
};

export type TestGeneratorResponse = {
  success?: boolean;
  message?: string;
  error?: {
    code?: string;
    message?: string;
  };
  data?: TestGeneratorResponseData;
};

export type ProcessStatus = "idle" | "inProgress" | "success" | "failed";

export interface UploadedFileMeta {
  uid: string;
  name: string;
  status: "done" | "uploading" | "error" | "removed";
  size?: number;
  type?: string;
}

export interface TestGenerationInputState {
  projectId: string | null;
  contextDocuments: ContextDocumentRequest[];
  impactPrompt: string;
  tableData: EpicGroup[];
  originalTableData: EpicGroup[];
  selectedStoryIds: string[];
  isJiraImport: boolean;
  hasInputFromPasteOrUpload: boolean;
  isFileUploaded: boolean;
  uploadedFiles: UploadedFileMeta[];
  hasSavedToDb: boolean;
}

export interface TestGenerationOutputState {
  testCaseStatuses: Record<string, TestCaseStatus>;
  expandedTestIds: Record<string, boolean>;
  storyPageById: Record<string, number>;
  hasPushed: boolean;
}

export interface TestGenerationState {
  status: ProcessStatus;
  error: string | null;
  generatedData: TestGeneratorResponseData | null;
  settings: GenerationSettings;
  generatedSettings: GenerationSettings | null;
  workflowStep: WorkflowStep;
  inputState: TestGenerationInputState;
  outputState: TestGenerationOutputState;
  lastUpdated: string | null;
}

export interface GenerateTestCasesSuccessPayload {
  generatedData: TestGeneratorResponseData;
  settings: GenerationSettings;
  message: string;
}
