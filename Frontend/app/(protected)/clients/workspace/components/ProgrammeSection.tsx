"use client";

import React from "react";
import Link from "next/link";
import { Button } from "antd";
import { Programme } from "@/types/programme";
import {
  formatISODate,
  getProgrammeStatusConfig,
} from "@/utils/programmes/programmeHelpers";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import { setActiveProgrammeId } from "@/utils/navContext";

interface ProgrammeSectionProps {
  programme: Programme;
  clientName: string;
  clientManager?: string;
  onEdit: () => void;
  onDelete: () => void;
}

export default function ProgrammeSection({
  programme,
  clientName,
  clientManager,
  onEdit,
  onDelete,
}: Readonly<ProgrammeSectionProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.PROGRAMME_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.PROGRAMME_DELETE);
  const programmePath = `/clients/programme?clientName=${encodeURIComponent(
    clientName,
  )}&programmeName=${encodeURIComponent(programme.name)}`;
  const { label, pillClass, dotClass } = getProgrammeStatusConfig(
    programme.status,
  );
  const projectCount =
    programme.projectCount ?? programme.projects?.length ?? 0;
  const lastModified = formatISODate(programme.lastModified);
  const managerDisplayName = programme.manager ?? clientManager ?? "Unassigned";

  return (
    <Link
      href={programmePath}
      className="programme-card__link"
      onClick={() => setActiveProgrammeId(programme.id)}
    >
      <div className="programme-card">
        <div className="programme-card__body">
          {/* Row 1 – Name */}
          <span className="programme-card__name">{programme.name}</span>

          {/* Row 2 – Status */}
          <div className="programme-card__status-row">
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {label}
            </span>
          </div>

          {/* Row 3 – Meta */}
          <div className="programme-card__meta">
            <span className="programme-card__meta-item">
              {projectCount} project{projectCount !== 1 ? "s" : ""}
            </span>
            <span className="programme-card__meta-sep">·</span>
            <span className="programme-card__meta-item">
              Manager: {managerDisplayName}
            </span>
            <span className="programme-card__meta-sep">·</span>
            <span className="programme-card__meta-item">
              Last modified: {lastModified}
            </span>
          </div>
        </div>

        {/* ── Action buttons (top-right, matching ClientCard) ── */}
        <div
          className="programme-card__actions"
          onClick={(e) => e.preventDefault()}
        >
          {canEdit && (
            <Button
              className="client-card__action-btn client-card__action-btn--edit"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onEdit();
              }}
              aria-label={`Edit ${programme.name}`}
            >
              Edit
            </Button>
          )}
          {canDelete && (
            <Button
              className="client-card__action-btn client-card__action-btn--delete"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete();
              }}
              aria-label={`Delete ${programme.name}`}
            >
              Delete
            </Button>
          )}
        </div>
      </div>
    </Link>
  );
}
