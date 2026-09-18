import type {
  Programme,
  ProgrammeApiErrorResponse,
  ProgrammeBackendRecord,
  ProgrammeServiceError,
} from "@/types/programme";
import {
  getProjectStatusConfig,
  mapBackendProject,
} from "@/utils/projects/projectHelpers";

export function isProgrammeApiError(
  body: unknown,
): body is ProgrammeApiErrorResponse {
  return (
    typeof body === "object" &&
    body !== null &&
    (("success" in body &&
      (body as Record<string, unknown>).success === false) ||
      ("error" in body &&
        typeof (body as Record<string, unknown>).error === "object"))
  );
}

export function programmeServiceError(opts: {
  message: string;
  code?: string;
  status?: number;
}): ProgrammeServiceError {
  const err = new Error(opts.message) as ProgrammeServiceError;
  if (opts.code) err.code = opts.code;
  if (opts.status) err.status = opts.status;
  return err;
}

export function isProgrammeServiceError(
  err: unknown,
): err is Error & { code?: string; status?: number } {
  return err instanceof Error;
}

export function formatISODate(dateStr?: string): string {
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

export function getProgrammeStatusConfig(status: string) {
  return getProjectStatusConfig(
    (status?.toLowerCase() as "active" | "onhold" | "complete") ?? "active",
  );
}

export function mapBackendProgramme(raw: ProgrammeBackendRecord): Programme {
  const rawManager = raw.manager_name || raw.manager;
  const manager =
    rawManager && rawManager !== "Unassigned" ? rawManager : undefined;
  return {
    id: String(raw.id),
    clientId: String(raw.client_id),
    name: raw.name,
    description: raw.description ?? undefined,
    status: raw.status ?? "active",
    manager,
    createdAt: raw.created_at ?? undefined,
    lastModified: raw.last_modified ?? undefined,
    projectCount: raw.project_count ?? 0,
    projects: (raw.projects ?? []).map(mapBackendProject),
  };
}
