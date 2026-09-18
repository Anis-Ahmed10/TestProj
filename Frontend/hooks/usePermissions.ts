"use client";

import { useCallback } from "react";
import { useAppSelector } from "@/store/store";
import type { Permission } from "@/constants";

export function usePermissions() {
  const user = useAppSelector((state) => state.auth.user);
  const status = useAppSelector((state) => state.auth.status);

  const hasPermission = useCallback(
    (permission: Permission) => user?.permissions.includes(permission) ?? false,
    [user],
  );

  return {
    user,
    role: user?.role ?? null,
    permissions: user?.permissions ?? [],
    hasPermission,
    isLoaded: status === "loaded",
    isResolving: status === "idle" || status === "loading",
    isError: status === "error",
  };
}
