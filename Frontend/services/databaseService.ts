import type { JiraEpic, SaveResult } from "@/types/jira";
import { apiRequest } from "@/utils/apiRequest/apiRequest";

import type { StoryChange } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
export type { StoryChange };

export interface StoryEditRecord {
  storyId: string;
  epicId: string;
  changes: StoryChange[];
  editedAt: string;
}

export interface StoryStatusEntry {
  already_exists: boolean;
  status: string;
}

// Look up existing DB status for story keys so non-Jira (Excel/CSV) imports get the
// same already-exists / approved / rejected / in-review signals as a Jira import.
export async function fetchStoryStatuses(
  projectId: string,
  storyKeys: string[],
): Promise<Record<string, StoryStatusEntry>> {
  if (!projectId || storyKeys.length === 0) return {};

  const body = await apiRequest<{
    statuses?: Record<string, StoryStatusEntry>;
  }>("/api/v1/database/story-statuses", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, story_keys: storyKeys }),
  });

  return body?.statuses ?? {};
}

async function withRetry<T>(
  fn: () => Promise<T>,
  retries: number,
  delayMs: number,
): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    if (retries === 0) throw err;
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    return withRetry(fn, retries - 1, delayMs * 2);
  }
}

export async function saveStoryEditLog(
  editLog: StoryEditRecord[],
): Promise<void> {
  if (editLog.length === 0) return;
  await withRetry(
    () =>
      apiRequest<unknown>("/api/v1/database/story-edit-log", {
        method: "POST",
        body: JSON.stringify({ edit_log: editLog }),
      }),
    2,
    1000,
  );
}

export async function saveStoriesToDb(
  selectedEpics: JiraEpic[],
  projectId: string,
): Promise<SaveResult> {
  if (!projectId) {
    throw new Error(
      "No project selected. Choose a project before saving stories.",
    );
  }

  // SaveResult.success is false for a partial save, which still carries the
  // inserted/skipped lists the caller renders — only HTTP failure is an error.
  return apiRequest<SaveResult>("/api/v1/database/save-stories", {
    method: "POST",
    body: JSON.stringify({
      selected_epics: selectedEpics,
      project_id: projectId,
    }),
    isError: () => false,
  });
}
