"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ProjectPage from "./components/ProjectPage";
import Link from "next/link";

function ProjectContent() {
  const searchParams = useSearchParams();
  const clientName = searchParams.get("clientName") ?? "";
  const programmeId = searchParams.get("programmeId") ?? "";
  const projectId = searchParams.get("projectId") ?? "";

  if (!clientName || !programmeId || !projectId) {
    return (
      <div className="workspace">
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Missing parameters</p>
          <p className="workspace__error-text">
            Client name, programme ID, or project ID was not provided.
          </p>
          <Link href="/clients" className="workspace__back-link">
            ← Back to Clients
          </Link>
        </div>
      </div>
    );
  }

  return (
    <ProjectPage
      clientName={clientName}
      programmeId={programmeId}
      projectId={projectId}
    />
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ProjectContent />
    </Suspense>
  );
}
