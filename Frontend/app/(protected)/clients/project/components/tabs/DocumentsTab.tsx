"use client";

import DocumentsSection from "@/app/(protected)/clients/components/DocumentsSection";

interface DocumentsTabProps {
  folderPath: string;
  entityId: string;
}

export default function DocumentsTab({
  folderPath,
  entityId,
}: DocumentsTabProps) {
  return (
    <div className="workspace__body">
      <div className="project-page__detail-card">
        <DocumentsSection
          folderPath={folderPath}
          entityId={entityId}
          heading="Project Documents"
          emptyDescription="Upload project-level documents — SOWs, specs, reports, and more."
        />
      </div>
    </div>
  );
}
