import type { ProjectApprover } from "@/types/user";
import { CurrentUser, MeApiResponse } from "@/types/auth";
import type { PlatformRole, PlatformUser } from "@/types/user";
import { apiRequest } from "@/utils/apiRequest/apiRequest";

export interface UserOption {
  value: string;
  label: string;
  role?: string | null;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const body = await apiRequest<MeApiResponse>("/api/v1/users/current-user", {
    method: "GET",
  });
  return body.data;
}

export async function fetchProjectApprovers(
  projectId: string,
): Promise<ProjectApprover[]> {
  const body = await apiRequest<{ data?: ProjectApprover[] }>(
    `/api/v1/users/approval-users?project_id=${encodeURIComponent(projectId)}`,
    { method: "GET" },
  );
  if (!Array.isArray(body?.data)) return [];
  return body.data
    .filter((approver) => typeof approver?.email === "string" && approver.email)
    .map((approver) => ({
      ...approver,
      name: approver.name || approver.email,
      role_label: approver.role_label ?? "",
    }));
}

export async function fetchPlatformUsers(): Promise<PlatformUser[]> {
  const body = await apiRequest<{ data?: PlatformUser[] }>("/api/v1/users", {
    method: "GET",
  });
  return Array.isArray(body?.data) ? body.data : [];
}

export async function fetchPlatformRoles(): Promise<PlatformRole[]> {
  const body = await apiRequest<{ data?: PlatformRole[] }>(
    "/api/v1/users/roles",
    { method: "GET" },
  );
  return Array.isArray(body?.data) ? body.data : [];
}

export async function updateUserRole(
  userId: string,
  role_name: string,
): Promise<void> {
  await apiRequest<unknown>(`/api/v1/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role_name }),
  });
}

export async function fetchUsers(): Promise<UserOption[]> {
  const users = await fetchPlatformUsers();
  return users.map((u) => ({
    value: String(u.id),
    label: u.name || String(u.id),
    role: u.role ?? undefined,
  }));
}

let assignableUsersPromise: Promise<UserOption[]> | null = null;

export function getAssignableUsers(): Promise<UserOption[]> {
  assignableUsersPromise ??= fetchUsers();
  return assignableUsersPromise;
}
