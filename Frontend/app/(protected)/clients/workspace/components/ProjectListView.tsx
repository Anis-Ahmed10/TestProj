"use client";

import React, { useMemo } from "react";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { Project } from "@/types/project";
import { formatISODate } from "@/utils/programmes/programmeHelpers";
import { getProjectStatusConfig } from "@/utils/projects/projectHelpers";
import AITable from "@/components/AITable";
import ListViewActions from "@/components/ListViewActions";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

interface ProjectListViewProps {
  projects: Project[];
  clientName: string;
  programmeId: string;
  onEdit: (project: Project) => void;
  onDelete: (project: Project) => void;
}

export default function ProjectListView({
  projects,
  clientName,
  programmeId,
  onEdit,
  onDelete,
}: Readonly<ProjectListViewProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.PROJECT_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.PROJECT_DELETE);

  const columns: ColumnsType<Project> = useMemo(
    () => [
      {
        title: "Project Name",
        dataIndex: "name",
        key: "name",
        ellipsis: true,
        render: (name: string, record) => {
          const projectPath = `/clients/project?clientName=${encodeURIComponent(
            clientName,
          )}&programmeId=${encodeURIComponent(
            programmeId,
          )}&projectId=${encodeURIComponent(
            record.id,
          )}&projectName=${encodeURIComponent(name)}`;
          return (
            <Link href={projectPath} className="clients-list-view__name-link">
              {name}
            </Link>
          );
        },
      },
      {
        title: "Status",
        dataIndex: "status",
        key: "status",
        width: 150,
        render: (status: Project["status"]) => {
          const { label, pillClass, dotClass } = getProjectStatusConfig(status);
          return (
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {label}
            </span>
          );
        },
      },
      {
        title: "Project Lead",
        key: "leadName",
        width: 180,
        ellipsis: true,
        render: (_, record) => record.leadName || "Unassigned",
      },
      {
        title: "Description",
        dataIndex: "description",
        key: "description",
        ellipsis: true,
        render: (description?: string) =>
          description ?? (
            <span className="clients-list-view__col--muted">—</span>
          ),
      },
      {
        title: "Last Modified",
        dataIndex: "lastModified",
        key: "lastModified",
        width: 150,
        render: (value: string) => formatISODate(value),
      },
      {
        title: "Actions",
        key: "actions",
        width: 150,
        render: (_, record) => (
          <ListViewActions
            name={record.name}
            onEdit={(e) => {
              e.stopPropagation();
              onEdit(record);
            }}
            onDelete={(e) => {
              e.stopPropagation();
              onDelete(record);
            }}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        ),
      },
    ],
    [onEdit, onDelete, clientName, programmeId, canEdit, canDelete],
  );

  return (
    <div className="clients-list-view">
      <AITable<Project>
        rowKey="id"
        columns={columns}
        datasource={projects}
        pageSize={10}
      />
    </div>
  );
}
