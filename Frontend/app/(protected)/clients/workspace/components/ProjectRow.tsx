"use client";

import React from "react";
import Link from "next/link";
import { Project } from "@/types/project";
import {
  formatProjectStartDate,
  getProjectStatusConfig,
} from "@/utils/projects/projectHelpers";

interface ProjectRowProps {
  project: Project;
  clientName: string;
  programmeId: string;
}

export default function ProjectRow({
  project,
  clientName,
  programmeId,
}: Readonly<ProjectRowProps>) {
  const { label, pillClass, dotClass } = getProjectStatusConfig(project.status);

  const projectPath = `/clients/project?clientName=${encodeURIComponent(
    clientName,
  )}&programmeId=${encodeURIComponent(
    programmeId,
  )}&projectId=${encodeURIComponent(
    project.id,
  )}&projectName=${encodeURIComponent(project.name)}`;
  return (
    <div className="project-table__row">
      <span className="project-table__col project-table__col--name">
        <Link href={projectPath} className="project-table__project-link">
          <span className="project-table__project-name">{project.name}</span>
        </Link>
      </span>

      <span className="project-table__col project-table__col--status">
        <span className={`project-status-pill ${pillClass}`}>
          <span className={`project-status-dot ${dotClass}`} />
          {label}
        </span>
      </span>

      <span className="project-table__col project-table__col--date">
        <span className="project-table__date">
          {formatProjectStartDate(project.startDate)}
        </span>
      </span>

      <span className="project-table__col project-table__col--desc">
        <span className="project-table__desc">
          {project.description ?? (
            <span className="project-table__no-desc">—</span>
          )}
        </span>
      </span>
    </div>
  );
}
