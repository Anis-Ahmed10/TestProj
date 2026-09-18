"use client";

import React from "react";
import Link from "next/link";
import { Button } from "antd";
import { Project } from "@/types/project";
import { formatISODate } from "@/utils/programmes/programmeHelpers";
import { getProjectStatusConfig } from "@/utils/projects/projectHelpers";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import { setActiveProgrammeId, setActiveProjectId } from "@/utils/navContext";
interface ProjectCardProps {
  project: Project;
  clientName: string;
  programmeId: string;
  programmeName: string;
  onEdit: (project: Project) => void;
  onDelete: (project: Project) => void;
}

export default function ProjectCard({
  project,
  clientName,
  programmeId,
  programmeName,
  onEdit,
  onDelete,
}: Readonly<ProjectCardProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.PROJECT_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.PROJECT_DELETE);
  const { label, pillClass, dotClass } = getProjectStatusConfig(project.status);
  const lastModified = formatISODate(project.lastModified);
  const projectPath = `/project-view?clientName=${encodeURIComponent(
    clientName,
  )}&programmeName=${encodeURIComponent(
    programmeName,
  )}&projectName=${encodeURIComponent(project.name)}`;

  return (
    <Link
      href={projectPath}
      className="programme-card__link"
      onClick={() => {
        setActiveProgrammeId(programmeId);
        setActiveProjectId(project.id);
      }}
    >
      <div className="project-card project-card--clickable">
        <div className="project-card__body">
          {/* Row 1 – Name */}
          <span className="project-card__name">{project.name}</span>

          {/* Row 2 – Status */}
          <div className="project-card__status-row">
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {label}
            </span>
          </div>

          {/* Row 3 – Meta */}
          <div className="project-card__meta">
            <span className="project-card__meta-item">
              Last modified: {lastModified}
            </span>

            <span className="project-card__meta-item">
              <strong>Lead:</strong> {project.leadName || "Unassigned"}
            </span>
          </div>
        </div>

        {/* ── Action buttons ── */}
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
                onEdit(project);
              }}
              aria-label={`Edit ${project.name}`}
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
                onDelete(project);
              }}
              aria-label={`Delete ${project.name}`}
            >
              Delete
            </Button>
          )}
        </div>
      </div>
    </Link>
  );
}
