import {
  TestCaseFormat,
  CoverageDepth,
  PriorityAssignment,
} from "@/types/testGenerator";

const formatOptions: TestCaseFormat[] = [
  "Structured (ID, Steps, Expected)",
  "BDD (Given/When/Then)",
  "Custom (User-defined template)",
];

const coverageOptions: CoverageDepth[] = [
  "Standard (Happy + Negative)",
  "Comprehensive (All paths)",
  "Smoke (Happy path only)",
];

const priorityOptions: PriorityAssignment[] = [
  "Auto-assign by risk",
  "All high",
  "Manual",
];

const ACCEPTED_FILE_TYPES = [".pdf", ".docx", ".xlsx", ".csv", ".txt"];
const MAX_SIZE_MB = 25;
const MAX_PDF_PAGES = 50;

const PERMISSIONS = {
  CLIENT_CREATE: "client:create",
  CLIENT_READ: "client:read",
  CLIENT_UPDATE: "client:update",
  CLIENT_DELETE: "client:delete",

  PROGRAMME_CREATE: "programme:create",
  PROGRAMME_READ: "programme:read",
  PROGRAMME_UPDATE: "programme:update",
  PROGRAMME_DELETE: "programme:delete",

  PROJECT_CREATE: "project:create",
  PROJECT_READ: "project:read",
  PROJECT_UPDATE: "project:update",
  PROJECT_DELETE: "project:delete",

  TESTCASE_GENERATE: "testcase:generate",
  TESTCASE_UPDATE: "testcase:update",
  TESTCASE_SAVE: "testcase:save",
  TESTCASE_SUMMARY_READ: "testcase:summary_read",
  TESTCASE_LIBRARY_READ: "testcase:library_read",

  AUTOMATION_ANALYZE: "automation:analyze",

  REGRESSION_READ: "regression:read",

  STORY_SAVE: "story:save",
  STORY_EDIT_LOG: "story:edit_log",
  STORY_REQUEST_APPROVAL: "story:request_approval",
  STORY_APPROVE: "story:approve",
  STORY_GET_PENDING_APPROVALS: "story:get_pending_approvals",
  STORY_GET_PROJECT_APPROVALS: "story:get_project_approvals",
  LIST_APPROVAL_USERS: "list:approval_users",

  DOCUMENT_UPLOAD: "document:upload",
  LIST_DOCUMENTS: "document:list",
  DOCUMENT_DELETE: "document:delete",

  LOGS_READ: "logs:read",

  JIRA_PUSH: "jira:push",
  JIRA_PULL: "jira:pull",
  JIRA_APPLY_REFRESH: "jira:apply_refresh",
  JIRA_REFRESH: "jira:refresh",
  JIRA_CONFIG_READ: "jira:config_read",
  JIRA_CONFIG_UPDATE: "jira:config_update",
  JIRA_TEST_CONNECTION: "jira:test_connection",

  TEAM_READ: "team:read",
  TEAM_ADD: "team:add",
  TEAM_REMOVE: "team:remove",
  TEAM_AVAILABLE_USERS: "team:available_users",

  USER_MANAGE: "user:manage",
} as const;

type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export {
  formatOptions,
  coverageOptions,
  priorityOptions,
  ACCEPTED_FILE_TYPES,
  MAX_SIZE_MB,
  MAX_PDF_PAGES,
  PERMISSIONS,
};
export type { Permission };
