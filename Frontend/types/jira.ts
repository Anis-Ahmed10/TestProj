export interface JiraStory {
  storyId: string;
  storyTitle: string;
  description: string;
  acceptanceCriteria?: string;
  issue_type: string;
  already_exists?: boolean;
  status?: string;
  priority?: string | null;
}

export interface JiraEpic {
  epicId: string;
  epicTitle: string;
  user_stories: JiraStory[];
}

export interface DisplayStory extends JiraStory {
  epicId: string;
  epicTitle: string;
  alreadyExists?: boolean;
  status?: string;
}

export interface SaveResult {
  success: boolean;
  inserted: string[];
  skipped: string[];
  updated: string[];
  failed: string[];
}

export interface RefreshResult {
  success: boolean;
  imported_count?: number;
  updated_count?: number;
  failed_count?: number;
  changed_story_keys: string[];
  new_story_keys: string[];
}

export interface ApplyRefreshResult {
  success: boolean;
  updated: string[];
}

export interface PushedTestCase {
  tc_id: string;
  jira_key: string | null;
  status: "pushed" | "duplicate" | "failed";
  rename_note?: string | null;
}

export interface PushToJiraResult {
  total: number;
  pushed_count: number;
  duplicate_count: number;
  failed_count: number;
  db_saved_count: number;
  pushed: PushedTestCase[];
  duplicates: string[];
  failed: Array<{
    tc_id: string;
    error: string;
  }>;
  db_skipped: string[];
  db_failed: string[];
}
