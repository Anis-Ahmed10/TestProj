import {
  apiRequest,
  type ApiErrorContext,
  ServiceError,
} from "@/utils/apiRequest/apiRequest";
import {
  isProgrammeApiError,
  programmeServiceError,
} from "@/utils/programmes/programmeHelpers";
import {
  CreateProjectResponse,
  Project,
  ProjectFormValues,
  ProjectStatus,
  UpdateProjectResponse,
  ProjectsApiResponse,
  BackendProject,
} from "@/types/project";
import type { ProjectUserStory } from "@/types/impactAnalyzer";

function mapProjectError({ response, body, cause }: ApiErrorContext): Error {
  if (isProgrammeApiError(body)) {
    return programmeServiceError({
      message:
        body.error?.message ??
        body.message ??
        `Project request failed (HTTP ${response?.status ?? "unknown"})`,
      code: body.error?.code,
      status: response?.status,
    });
  }
  if (cause instanceof Error) return cause;
  return new ServiceError(
    response ? `Request failed (${response.status})` : "Network request failed",
    { status: response?.status },
  );
}

export async function createProject(
  programmeId: string,
  values: ProjectFormValues,
): Promise<Project> {
  const response = await apiRequest<CreateProjectResponse>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({
      programme_id: programmeId,
      name: values.name.trim(),
      description: values.description?.trim() || null,
      status: values.status,
      lead_id: values.leadId || null,
    }),
    mapError: mapProjectError,
  });

  const data = response.data;
  return {
    id: String(data.id),
    name: data.name ?? values.name.trim(),
    description: data.description ?? values.description?.trim() ?? undefined,
    status: (data.status as ProjectStatus | undefined) ?? values.status,
    leadId: data.lead_id ?? values.leadId ?? undefined,
    leadName: data.lead_name ?? "Unassigned",
    startDate: data.start_date ?? undefined,
  };
}

export async function fetchProjects(): Promise<BackendProject[]> {
  const response = await apiRequest<ProjectsApiResponse>("/api/v1/projects", {
    method: "GET",
    cache: "no-store",
    mapError: mapProjectError,
  });

  if (!response?.success || !Array.isArray(response.data)) {
    throw new Error("Unexpected response format from projects API");
  }

  return response.data;
}

export interface ProjectTestCaseSummary {
  total: number;
  approved: number;
  pending: number;
  archived: number;
  pass_rate: number;
}

export async function fetchProjectTestCaseSummary(
  projectId: string,
): Promise<ProjectTestCaseSummary> {
  const response = await apiRequest<{ data: ProjectTestCaseSummary }>(
    `/api/v1/test-cases/project/${encodeURIComponent(projectId)}/summary`,
    {
      method: "GET",
      cache: "no-store",
      mapError: mapProjectError,
    },
  );

  if (!response?.data || typeof response.data.total !== "number") {
    throw new Error("Test case summary response was malformed.");
  }

  return response.data;
}

export async function fetchProjectUserStories(
  projectId: string,
): Promise<ProjectUserStory[]> {
  const payload = await apiRequest<{ data?: ProjectUserStory[] }>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/user-stories`,
    {
      method: "GET",
      cache: "no-store",
      isError: isProgrammeApiError,
      mapError: mapProjectError,
    },
  );

  if (!Array.isArray(payload?.data)) {
    throw new Error("Unexpected response format from user stories API");
  }
  return payload.data;
}

export async function updateProjectById(
  projectId: string,
  payload: {
    name?: string;
    description?: string;
    status?: string;
    lead_id?: string | null;
  },
): Promise<Project> {
  const response = await apiRequest<UpdateProjectResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      mapError: mapProjectError,
    },
  );

  const data = response.data;
  return {
    id: String(data.id),
    name: data.name ?? "",
    description: data.description ?? undefined,
    status: (data.status as ProjectStatus | undefined) ?? "active",
    leadId: data.lead_id ?? undefined,
    leadName: data.lead_name ?? "Unassigned",
    lastModified: data.last_modified ?? undefined,
  };
}

export async function deleteProjectById(projectId: string): Promise<void> {
  await apiRequest<void>(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
    mapError: mapProjectError,
  });
}
