import { ProgrammeApiSuccessResponse } from "./programme";

export const PROJECT_STATUS_OPTIONS = ["active", "onhold", "complete"] as const;
export type ProjectStatus = (typeof PROJECT_STATUS_OPTIONS)[number];

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  active: "Active",
  onhold: "On Hold",
  complete: "Complete",
};

export interface ProjectBackendRecord {
  id: string;
  programme_id?: string | null;
  name: string;
  description?: string | null;
  status: string;
  lead_id?: string | null;
  lead_name?: string | null;
  start_date?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
}

export interface Project {
  id: string;
  programmeId?: string | null;
  name: string;
  description?: string | null;
  status: ProjectStatus;
  leadId?: string | null;
  leadName?: string | null;
  startDate?: string | null;
  createdAt?: string;
  lastModified?: string;
}

export interface ProjectFormValues {
  name: string;
  description: string;
  status: ProjectStatus;
  leadId?: string;
}

export interface ProjectFormErrors {
  name?: string;
  status?: string;
}

export type CreateProjectResponse = ProgrammeApiSuccessResponse<{
  id: string;
  programme_id: string;
  name: string;
  description?: string | null;
  status?: string;
  lead_id?: string | null;
  lead_name?: string | null;
  start_date?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
}>;

export interface BackendProject {
  id: string;
  name: string;
  programme_id: string;
  programme_name: string;
  client_id: string;
  client_name: string;
  description?: string | null;
  status?: string | null;
  lead_id?: string | null;
  lead_name?: string | null;
  start_date?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
}

export interface ProjectsApiResponse {
  success: boolean;
  data: BackendProject[];
}

export type UpdateProjectResponse = ProgrammeApiSuccessResponse<{
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  lead_id?: string | null;
  lead_name?: string | null;
  last_modified?: string | null;
}>;

export type TabId =
  | "overview"
  | "ai-tools"
  | "jira-integration"
  | "documents"
  | "team"
  | "logs";

export const PROJECT_TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "ai-tools", label: "AI Tools" },
  { id: "jira-integration", label: "Jira Integration" },
  { id: "documents", label: "Documents" },
  { id: "team", label: "Team" },
  { id: "logs", label: "Logs" },
];
