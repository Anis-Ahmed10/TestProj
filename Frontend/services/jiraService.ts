import type {
  JiraEpic,
  DisplayStory,
  RefreshResult,
  PushToJiraResult,
  ApplyRefreshResult,
} from "@/types/jira";
import type { FlatTestCase, GenerationSettings } from "@/types/testGenerator";
import { sanitizeEpicsPayload } from "@/utils/sanitizer/pipeline";
import { toBackendFormat } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

export class JiraNotConfiguredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JiraNotConfiguredError";
  }
}

function extractErrorInfo(body: unknown): { code?: string; message?: string } {
  if (!body || typeof body !== "object") return {};
  const anyBody = body as Record<string, unknown>;
  const error = anyBody.error as Record<string, unknown> | undefined;
  if (error && typeof error.message === "string") {
    return {
      code: typeof error.code === "string" ? error.code : undefined,
      message: error.message,
    };
  }
  if (typeof anyBody.detail === "string") {
    return { message: anyBody.detail };
  }
  return {};
}

function jiraError(base: string) {
  return ({ response, body, cause }: ApiErrorContext): Error => {
    if (!response) {
      return cause instanceof Error ? cause : new Error(base);
    }
    const { code, message } = extractErrorInfo(body);
    if (code === "JIRA_NOT_CONFIGURED") {
      return new JiraNotConfiguredError(
        message ?? "Jira credentials aren't set up for this project yet.",
      );
    }
    return new Error(message ?? `${base} (${response.status})`);
  };
}

export interface JiraConfig {
  jiraUrl: string;
  projectKey: string;
  isConnected: boolean;
}

function mapJiraConfig(data: Record<string, unknown>): JiraConfig {
  return {
    jiraUrl: (data.jira_url as string) ?? "",
    projectKey: (data.project_key as string) ?? "",
    isConnected: Boolean(data.is_connected),
  };
}

export async function getJiraConfig(projectId: string): Promise<JiraConfig> {
  const data = await apiRequest<Record<string, unknown>>(
    `/api/v1/jira/config/${projectId}`,
    {
      method: "GET",
      isError: () => false,
      mapError: jiraError("Failed to load Jira config"),
    },
  );
  return mapJiraConfig(data);
}

export async function saveJiraConfig(
  projectId: string,
  config: { jiraUrl: string; projectKey: string },
): Promise<JiraConfig> {
  const data = await apiRequest<Record<string, unknown>>(
    `/api/v1/jira/config/${projectId}`,
    {
      method: "PUT",
      body: JSON.stringify({
        jira_url: config.jiraUrl,
        project_key: config.projectKey,
      }),
      isError: () => false,
      mapError: jiraError("Failed to save Jira config"),
    },
  );
  return mapJiraConfig(data);
}

export interface JiraCredentials {
  jiraEmail: string;
  hasApiToken: boolean;
}

function mapJiraCredentials(data: Record<string, unknown>): JiraCredentials {
  return {
    jiraEmail: (data.jira_email as string) ?? "",
    hasApiToken: Boolean(data.has_api_token),
  };
}

export async function getMyJiraCredentials(): Promise<JiraCredentials> {
  const data = await apiRequest<Record<string, unknown>>(
    "/api/v1/jira/my-credentials",
    {
      method: "GET",
      isError: () => false,
      mapError: jiraError("Failed to load Jira credentials"),
    },
  );
  return mapJiraCredentials(data);
}

export async function saveMyJiraCredentials(credentials: {
  jiraEmail: string;
  apiToken?: string;
}): Promise<JiraCredentials> {
  const data = await apiRequest<Record<string, unknown>>(
    "/api/v1/jira/my-credentials",
    {
      method: "PUT",
      body: JSON.stringify({
        jira_email: credentials.jiraEmail,
        api_token: credentials.apiToken,
      }),
      isError: () => false,
      mapError: jiraError("Failed to save Jira credentials"),
    },
  );
  return mapJiraCredentials(data);
}

export async function testJiraConnection(
  projectId: string,
): Promise<{ success: boolean; message: string }> {
  return apiRequest<{ success: boolean; message: string }>(
    `/api/v1/jira/test-connection/${projectId}`,
    {
      method: "POST",
      isError: () => false,
      mapError: jiraError("Test connection failed"),
    },
  );
}

function statusQuery(statuses: string[]): string {
  const q = statuses
    .filter((s) => s.trim())
    .map((s) => `status=${encodeURIComponent(s)}`)
    .join("&");
  return q ? `?${q}` : "";
}

export async function getJiraStatuses(projectId: string): Promise<string[]> {
  return apiRequest<string[]>(`/api/v1/jira/statuses/${projectId}`, {
    method: "GET",
    isError: () => false,
    mapError: jiraError("Failed to load Jira statuses"),
  });
}

async function fetchJiraIssues(
  projectId: string,
  statuses: string[] = [],
): Promise<JiraEpic[]> {
  return apiRequest<JiraEpic[]>(
    `/api/v1/jira/fetch-issues/${projectId}${statusQuery(statuses)}`,
    {
      method: "GET",
      isError: () => false,
      mapError: jiraError("Jira fetch failed"),
    },
  );
}

function sanitiseAndFlatten(epics: JiraEpic[]): DisplayStory[] {
  const sanitisable = epics.map((epic) => ({
    [epic.epicId]: {
      epicTitle: epic.epicTitle,
      stories: epic.user_stories.map((s) => ({
        storyTitle: s.storyTitle,
        description: s.description,
        acceptanceCriteria: s.acceptanceCriteria ? [s.acceptanceCriteria] : [],
      })),
    },
  }));

  const sanitised = sanitizeEpicsPayload(sanitisable);

  const result: DisplayStory[] = [];

  sanitised.forEach((entry, epicIndex) => {
    const epicKey = Object.keys(entry)[0];
    const sanitizedEpic = entry[epicKey];
    const originalEpic = epics[epicIndex];

    sanitizedEpic.stories?.forEach((story, storyIndex) => {
      const originalStory = originalEpic.user_stories[storyIndex];

      result.push({
        storyId: originalStory.storyId,
        epicId: epicKey,
        epicTitle: sanitizedEpic.epicTitle ?? originalEpic.epicTitle,
        storyTitle: story.storyTitle ?? originalStory.storyTitle,
        description: story.description ?? "",
        acceptanceCriteria: story.acceptanceCriteria?.[0],
        issue_type: originalStory.issue_type,
        alreadyExists: originalStory.already_exists,
        status: originalStory.status,
        priority: originalStory.priority ?? null,
      });
    });
  });

  return result;
}

export async function fetchAllFromJira(
  projectId: string,
  statuses: string[] = [],
): Promise<{
  stories: DisplayStory[];
  epics: JiraEpic[];
  totalStories: number;
  totalEpics: number;
}> {
  const epics = await fetchJiraIssues(projectId, statuses);
  const stories = sanitiseAndFlatten(epics);

  return {
    stories,
    epics,
    totalStories: stories.length,
    totalEpics: epics.length,
  };
}

export async function refreshFromJira(
  projectId: string,
  statuses: string[] = [],
): Promise<RefreshResult> {
  return apiRequest<RefreshResult>(
    `/api/v1/jira/refresh-imported-stories/${projectId}${statusQuery(
      statuses,
    )}`,
    {
      method: "GET",
      isError: () => false,
      mapError: jiraError("Refresh failed"),
    },
  );
}

export async function applyRefreshChanges(
  projectId: string,
  statuses: string[] = [],
  epicsPayload?: JiraEpic[],
): Promise<ApplyRefreshResult> {
  return apiRequest<ApplyRefreshResult>(
    `/api/v1/jira/apply-refresh-changes/${projectId}${statusQuery(statuses)}`,
    {
      method: "POST",
      body: epicsPayload ? JSON.stringify(epicsPayload) : undefined,
      isError: () => false,
      mapError: jiraError("Apply refresh changes failed"),
    },
  );
}

export async function pushTestCasesToJira(
  projectId: string,
  userStoryId: string,
  testCases: FlatTestCase[],
  format: GenerationSettings["format"],
): Promise<PushToJiraResult> {
  return apiRequest<PushToJiraResult>("/api/v1/jira/push-to-jira", {
    method: "POST",
    body: JSON.stringify({
      userStoryId,
      projectId,
      format: toBackendFormat(format),
      test_cases: testCases.map(buildTestCasePayload),
    }),
    isError: () => false,
    mapError: jiraError("Push to Jira failed"),
  });
}

export async function pushAllUserStoryTestCases(
  projectId: string,
  testCases: FlatTestCase[],
  format: GenerationSettings["format"],
): Promise<PushToJiraResult> {
  const byStory = new Map<string, FlatTestCase[]>();

  testCases.forEach((tc) => {
    if (!byStory.has(tc.storyId)) {
      byStory.set(tc.storyId, []);
    }

    byStory.get(tc.storyId)!.push(tc);
  });

  const merged: PushToJiraResult = {
    total: testCases.length,
    pushed_count: 0,
    duplicate_count: 0,
    failed_count: 0,
    db_saved_count: 0,
    pushed: [],
    duplicates: [],
    failed: [],
    db_skipped: [],
    db_failed: [],
  };

  for (const [storyId, cases] of byStory.entries()) {
    const result = await pushTestCasesToJira(projectId, storyId, cases, format);

    merged.pushed_count += result.pushed_count;
    merged.duplicate_count += result.duplicate_count;
    merged.failed_count += result.failed_count;
    merged.db_saved_count += result.db_saved_count;

    merged.pushed.push(...result.pushed);
    merged.duplicates.push(...result.duplicates);
    merged.failed.push(...result.failed);
    merged.db_skipped.push(...result.db_skipped);
    merged.db_failed.push(...result.db_failed);
  }

  return merged;
}

function buildTestCasePayload(tc: FlatTestCase): Record<string, unknown> {
  return {
    id: tc.testCaseKey || tc.id,
    title: tc.title,
    priority: tc.priority ?? "Medium",
    steps: tc.steps ?? null,
    expected: tc.expectedResult ?? null,
    scenario: tc.scenario
      ? {
          given: tc.scenario.given ?? [],
          when: tc.scenario.when ?? [],
          then: tc.scenario.then ?? [],
        }
      : null,
    tags: tc.tags ?? null,
    preconditions: tc.preconditions ?? null,
  };
}
