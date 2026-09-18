import { apiRequest } from "@/utils/apiRequest/apiRequest";

export interface TeamMember {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  hours_this_sprint?: number | null;
  status: string;
}

export interface AvailableUser {
  id: string;
  name: string;
  email: string;
  role?: string;
}

export async function fetchProjectTeamMembers(
  projectId: string,
): Promise<TeamMember[]> {
  const body = await apiRequest<{ data: TeamMember[] }>(
    `/api/v1/projects/${projectId}/team`,
    { method: "GET" },
  );
  return body.data;
}

export async function fetchAvailableUsers(
  projectId: string,
): Promise<AvailableUser[]> {
  const body = await apiRequest<{ data: AvailableUser[] }>(
    `/api/v1/projects/${projectId}/team/available-users`,
    { method: "GET" },
  );
  return body.data;
}

/** Add selected user IDs to the project team. */
export async function addTeamMembers(
  projectId: string,
  userIds: string[],
): Promise<TeamMember[]> {
  const body = await apiRequest<{ data: TeamMember[] }>(
    `/api/v1/projects/${projectId}/team`,
    { method: "POST", body: JSON.stringify({ user_ids: userIds }) },
  );
  return body.data;
}

/** Remove a single user from the project team. */
export async function removeTeamMember(
  projectId: string,
  userId: string,
): Promise<{ name: string }> {
  const body = await apiRequest<{ data: { name: string } }>(
    `/api/v1/projects/${projectId}/team/${userId}`,
    { method: "DELETE" },
  );
  return body.data;
}
