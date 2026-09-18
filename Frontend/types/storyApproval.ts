export interface StoryApprovalRecord {
  id: string;
  user_story_id: string;
  project_id: string;
  submitted_by: string;
  reviewer_email: string;
  status: "pending" | "approved" | "rejected";
  submitted_at: string;
  decided_at: string | null;
}

export interface StoryApprovalSkippedPair {
  user_story_id: string;
  reviewer_email: string;
}

export interface ApprovalStory {
  storyId: string;
  storyTitle: string;
  description: string;
  acceptanceCriteria: string;
  issue_type: string;
  priority?: string | null;
}

export interface ApprovalEpic {
  epicId: string;
  epicTitle: string;
  user_stories: ApprovalStory[];
}

export interface StoryApprovalSubmitResult {
  submitted_count: number;
  skipped_count: number;
  approval_records: StoryApprovalRecord[];
  skipped_pairs: StoryApprovalSkippedPair[];
}

export type ReviewDecision = "approved" | "rejected";

export interface ReviewStory {
  id: string; // approval id — the key for decisions
  user_story_id: string; // business story key, e.g. AEI-101
  project_id: string;
  project_name: string;
  epic_id: string | null;
  epic_title: string | null;
  title: string;
  description: string;
  acceptance_criteria: string[];
  priority: string | null;
  submitted_by: string;
  submitted_at: string;
  status: "pending" | "approved" | "rejected";
  decided_at: string | null;
  // Name of the reviewer who approved/rejected the story. Null while pending.
  decided_by_name: string | null;
}

export interface ReviewQueueCounts {
  pending: number;
  approved: number;
  rejected: number;
}

export interface ReviewQueueFacet {
  id: string;
  label: string;
}

export interface ReviewQueueFacets {
  projects: ReviewQueueFacet[];
  epics: ReviewQueueFacet[];
}

export interface ReviewQueueResponse {
  stories: ReviewStory[];
  counts: ReviewQueueCounts;
  total: number;
  facets: ReviewQueueFacets;
}
