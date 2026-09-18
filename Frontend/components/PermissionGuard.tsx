"use client";

import React from "react";
import Link from "next/link";
import { usePermissions } from "@/hooks/usePermissions";
import { useAppDispatch } from "@/store/store";
import { clearAuth } from "@/store/slices/authSlice";
import type { Permission } from "@/constants";

interface PermissionGuardProps {
  permission: Permission;
  children: React.ReactNode;
}

export default function PermissionGuard({
  permission,
  children,
}: PermissionGuardProps) {
  const dispatch = useAppDispatch();
  const { hasPermission, isLoaded, isResolving, isError } = usePermissions();

  if (isResolving) {
    return null;
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
        <h2 className="text-xl font-semibold text-gray-800">
          Unable to verify your access
        </h2>
        <p className="text-gray-500 max-w-md">
          We couldn&apos;t load your account details. Please try again, or
          contact an administrator if the problem persists.
        </p>
        <button
          type="button"
          onClick={() => dispatch(clearAuth())}
          className="text-[#1f5c54] font-medium underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (isLoaded && hasPermission(permission)) {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
      <h2 className="text-xl font-semibold text-gray-800">
        You don&apos;t have access to this page
      </h2>
      <p className="text-gray-500 max-w-md">
        Your current role doesn&apos;t include the permission required to view
        this area. Contact an administrator if you believe this is a mistake.
      </p>
      <Link href="/" className="text-[#1f5c54] font-medium underline">
        Go back home
      </Link>
    </div>
  );
}
