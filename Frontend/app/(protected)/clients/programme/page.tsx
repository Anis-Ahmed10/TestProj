"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ProgrammePage from "./components/ProgrammePage";
import Link from "next/link";

function ProgrammeContent() {
  const searchParams = useSearchParams();
  const clientName = searchParams.get("clientName") ?? "";
  const programmeName = searchParams.get("programmeName") ?? "";

  if (!clientName || !programmeName) {
    return (
      <div className="workspace">
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Missing parameters</p>
          <p className="workspace__error-text">
            Client name or programme name was not provided.
          </p>
          <Link href="/clients" className="workspace__back-link">
            ← Back to Clients
          </Link>
        </div>
      </div>
    );
  }

  return (
    <ProgrammePage clientName={clientName} programmeName={programmeName} />
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ProgrammeContent />
    </Suspense>
  );
}
