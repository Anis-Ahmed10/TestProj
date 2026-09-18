import type {
  ApprovalEpic,
  ReviewDecision,
  ReviewQueueResponse,
  ReviewStory,
  StoryApprovalRecord,
  StoryApprovalSubmitResult,
} from "@/types/storyApproval";
import { apiRequest } from "@/utils/apiRequest/apiRequest";

export interface ReviewQueueFilters {
  status?: string;
  projectId?: string;
  epicId?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

// The review-queue payload is typed here but produced elsewhere: a missing
// container key or a null row field crashes the table on render (the UI calls
// .map/.length/.toLowerCase on these). Default them once at the boundary so no
// caller has to null-check.
function normalizeQueue(raw: unknown): ReviewQueueResponse {
  const data = (raw ?? {}) as Partial<ReviewQueueResponse>;
  return {
    stories: (data.stories ?? []).map((s: Partial<ReviewStory>) => ({
      ...(s as ReviewStory),
      title: s.title ?? "",
      description: s.description ?? "",
      acceptance_criteria: s.acceptance_criteria ?? [],
      submitted_by: s.submitted_by ?? "Unknown",
      status: s.status ?? "pending",
      priority: s.priority ?? null,
      decided_at: s.decided_at ?? null,
      decided_by_name: s.decided_by_name ?? null,
    })),
    counts: data.counts ?? { pending: 0, approved: 0, rejected: 0 },
    total: data.total ?? 0,
    facets: {
      projects: data.facets?.projects ?? [],
      epics: data.facets?.epics ?? [],
    },
  };
}

export async function fetchReviewQueue(
  filters: ReviewQueueFilters = {},
): Promise<ReviewQueueResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.projectId) params.set("project_id", filters.projectId);
  if (filters.epicId) params.set("epic_id", filters.epicId);
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.page) params.set("page", String(filters.page));
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  const query = params.toString();

  const body = await apiRequest<{ data?: unknown }>(
    `/api/v1/story-approvals/review-queue${query ? `?${query}` : ""}`,
    { method: "GET" },
  );
  return normalizeQueue(body?.data);
}

export async function decideStory(
  approvalId: string,
  decision: ReviewDecision,
): Promise<StoryApprovalRecord> {
  const body = await apiRequest<{ data: StoryApprovalRecord }>(
    `/api/v1/story-approvals/${approvalId}/decision`,
    { method: "PATCH", body: JSON.stringify({ decision }) },
  );
  return body.data;
}

export async function submitStoriesForApproval(
  epics: ApprovalEpic[],
  projectId: string,
  reviewerEmails: string[],
): Promise<StoryApprovalSubmitResult> {
  const body = await apiRequest<{ data: StoryApprovalSubmitResult }>(
    "/api/v1/story-approvals",
    {
      method: "POST",
      body: JSON.stringify({
        epics,
        project_id: projectId,
        reviewer_emails: reviewerEmails,
      }),
    },
  );
  return body.data;
}
