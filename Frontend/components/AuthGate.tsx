"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthSession } from "aws-amplify/auth";

type GateStatus = "checking" | "authenticated";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<GateStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    fetchAuthSession()
      .then((session) => {
        if (cancelled) return;
        if (session.tokens?.idToken) {
          setStatus("authenticated");
        } else {
          router.replace("/login");
        }
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (status !== "authenticated") {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0f1117] text-gray-300">
        <span className="text-sm">Checking your session…</span>
      </div>
    );
  }

  return <>{children}</>;
}
