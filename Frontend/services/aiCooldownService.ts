import { fetchApplicationLogs } from "@/services/applicationlogsservice";
import {
  AI_COOLDOWN_LOG_SERVICE_NAME,
  type AiCooldownServiceName,
} from "@/types/aiCooldown";

export async function getLastTriggeredAt(
  service: AiCooldownServiceName,
): Promise<Date | null> {
  const expectedEndpoint = `/${service}`;
  const { logs } = await fetchApplicationLogs({
    service: AI_COOLDOWN_LOG_SERVICE_NAME,
    limit: 20,
  });

  const mostRecentSuccess = logs
    .filter(
      (entry) =>
        entry.statusCode === 200 && entry.endpoint === expectedEndpoint,
    )
    .sort(
      (a, b) => new Date(b.loggedAt).getTime() - new Date(a.loggedAt).getTime(),
    )[0];

  return mostRecentSuccess ? new Date(mostRecentSuccess.loggedAt) : null;
}
