import { apiRequest } from "@/utils/apiRequest/apiRequest";

export interface ApplicationLogEntry {
  id: string;
  loggedAt: string;
  serviceName: string;
  userId: string | null;
  userEmail: string | null;
  userName: string | null;
  endpoint: string;
  statusCode: number | null;
  message: string | null;
}

export async function fetchApplicationLogs(params: {
  projectId?: string;
  service?: string;
  limit?: number;
  offset?: number;
}): Promise<{ logs: ApplicationLogEntry[]; total: number }> {
  const query = new URLSearchParams();
  if (params.projectId) query.set("project_id", params.projectId);
  if (params.service) query.set("service", params.service);
  query.set("limit", String(params.limit ?? 100));
  query.set("offset", String(params.offset ?? 0));

  const body = await apiRequest<{
    data?: { logs?: Record<string, unknown>[]; total?: number };
  }>(`/api/v1/logs?${query.toString()}`, {
    method: "GET",
    signal: AbortSignal.timeout(15000),
  });

  const data = body?.data ?? { logs: [], total: 0 };

  return {
    total: data.total ?? 0,
    logs: (data.logs ?? []).map((entry): ApplicationLogEntry => {
      const asStringOrNull = (v: unknown): string | null =>
        typeof v === "string" ? v : null;
      return {
        id: String(entry.id),
        loggedAt: String(entry.logged_at),
        serviceName: String(entry.service_name ?? ""),
        userId: asStringOrNull(entry.user_id),
        userEmail: asStringOrNull(entry.user_email),
        userName: asStringOrNull(entry.user_name),
        endpoint: String(entry.endpoint ?? ""),
        statusCode:
          typeof entry.status_code === "number" ? entry.status_code : null,
        message: asStringOrNull(entry.message),
      };
    }),
  };
}
