"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getLastTriggeredAt } from "@/services/aiCooldownService";
import type { AiCooldownServiceName } from "@/types/aiCooldown";

// Cooldown window: 5 minutes from the most recent successful application_logs
export const AI_COOLDOWN_DURATION_SECONDS = 300;

export function formatCooldown(totalSeconds: number): string {
  const clamped = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(
    2,
    "0",
  )}`;
}

export interface UseActionCooldownResult {
  isCoolingDown: boolean;
  remainingSeconds: number;
  formatted: string;
  refresh: () => Promise<void>;
}

export function useActionCooldown(
  service: AiCooldownServiceName,
): UseActionCooldownResult {
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const applyLastTriggeredAt = useCallback((lastTriggeredAt: Date | null) => {
    if (!lastTriggeredAt) {
      setExpiresAt(null);
      return;
    }
    const expiry =
      lastTriggeredAt.getTime() + AI_COOLDOWN_DURATION_SECONDS * 1000;
    setExpiresAt(expiry > Date.now() ? expiry : null);
    setNow(Date.now());
  }, []);

  const refresh = useCallback(async () => {
    try {
      const lastTriggeredAt = await getLastTriggeredAt(service);
      applyLastTriggeredAt(lastTriggeredAt);
    } catch (err) {
      console.warn(
        "[ai-cooldown] failed to read application_logs, retrying once",
        service,
        err,
      );
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const lastTriggeredAt = await getLastTriggeredAt(service);
        applyLastTriggeredAt(lastTriggeredAt);
      } catch (retryErr) {
        console.warn(
          "[ai-cooldown] retry also failed to read application_logs",
          service,
          retryErr,
        );
      }
    }
  }, [service, applyLastTriggeredAt]);

  useEffect(() => {
    let cancelled = false;
    getLastTriggeredAt(service)
      .then((lastTriggeredAt) => {
        if (!cancelled) applyLastTriggeredAt(lastTriggeredAt);
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn(
            "[ai-cooldown] failed to restore from application_logs",
            service,
            err,
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [service, applyLastTriggeredAt]);

  useEffect(() => {
    if (expiresAt === null) return;
    setNow(Date.now());
    const id = setInterval(() => {
      if (Date.now() >= expiresAt) {
        setExpiresAt(null);
        return;
      }
      setNow(Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  const remainingSeconds =
    expiresAt === null ? 0 : Math.max(0, Math.ceil((expiresAt - now) / 1000));

  return useMemo(
    () => ({
      isCoolingDown: remainingSeconds > 0,
      remainingSeconds,
      formatted: formatCooldown(remainingSeconds),
      refresh,
    }),
    [remainingSeconds, refresh],
  );
}
