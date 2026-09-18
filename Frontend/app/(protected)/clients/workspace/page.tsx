"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ClientWorkspacePage from "./components/ClientWorkspacePage";
import Link from "next/link";

function WorkspaceContent() {
  const searchParams = useSearchParams();
  const clientName = searchParams.get("clientName") ?? "";

  if (!clientName) {
    return (
      <div className="workspace">
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Missing client name</p>
          <p className="workspace__error-text">
            No client was specified. Please return to the clients list.
          </p>
          <Link href="/clients" className="workspace__back-link">
            ← Back to Clients
          </Link>
        </div>
      </div>
    );
  }

  return <ClientWorkspacePage clientName={clientName} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <WorkspaceContent />
    </Suspense>
  );
}
