import { Project, ProjectStatus } from "@/types/project";
export function normalizeProjectStatus(raw: string): ProjectStatus {
  const map: Record<string, ProjectStatus> = {
    active: "active",
    onhold: "onhold",
    "on hold": "onhold",
    complete: "complete",
    completed: "complete",
  };
  return map[raw?.toLowerCase?.() ?? ""] ?? "active";
}
export const PROJECT_STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; pillClass: string; dotClass: string }
> = {
  active: {
    label: "Active",
    pillClass: "project-status-pill--active",
    dotClass: "project-status-dot--active",
  },
  onhold: {
    label: "On Hold",
    pillClass: "project-status-pill--onhold",
    dotClass: "project-status-dot--onhold",
  },
  complete: {
    label: "Complete",
    pillClass: "project-status-pill--complete",
    dotClass: "project-status-dot--complete",
  },
};

export function getProjectStatusConfig(status: ProjectStatus) {
  return PROJECT_STATUS_CONFIG[status] ?? PROJECT_STATUS_CONFIG.active;
}

export function formatProjectStartDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}
export interface ProjectValidationErrors {
  name?: string;
  description?: string;
  status?: string;
}

export function validateProjectForm(values: {
  name: string;
  status: string;
}): ProjectValidationErrors {
  const errors: ProjectValidationErrors = {};
  if (!values.name.trim()) errors.name = "Project name is required.";
  else if (values.name.trim().length > 50)
    errors.name = "Name must be 50 characters or fewer.";
  if (!values.status) errors.status = "Status is required.";
  return errors;
}

export function mapBackendProject(raw: any): Project {
  return {
    id: String(raw.id),
    name: raw.name,
    description: raw.description ?? undefined,
    status: normalizeProjectStatus(raw.status),
    leadId: raw.lead_id ?? raw.leadId ?? undefined,
    leadName: raw.lead_name ?? raw.leadName ?? "Unassigned",
    startDate: raw.start_date ?? undefined,
    createdAt: raw.created_at ?? undefined,
    lastModified: raw.last_modified ?? undefined,
  };
}
