"use client";

import React, { useMemo } from "react";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { Programme } from "@/types/programme";
import {
  formatISODate,
  getProgrammeStatusConfig,
} from "@/utils/programmes/programmeHelpers";
import AITable from "@/components/AITable";
import ListViewActions from "@/components/ListViewActions";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import { setActiveProgrammeId } from "@/utils/navContext";

interface ProgrammeListViewProps {
  programmes: Programme[];
  clientName: string;
  onEdit: (programme: Programme) => void;
  onDelete: (programme: Programme) => void;
}

export default function ProgrammeListView({
  programmes,
  clientName,
  onEdit,
  onDelete,
}: Readonly<ProgrammeListViewProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.PROGRAMME_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.PROGRAMME_DELETE);

  const columns: ColumnsType<Programme> = useMemo(
    () => [
      {
        title: "Programme Name",
        dataIndex: "name",
        key: "name",
        ellipsis: true,
        render: (name: string, record) => {
          const programmePath = `/clients/programme?clientName=${encodeURIComponent(
            clientName,
          )}&programmeName=${encodeURIComponent(name)}`;
          return (
            <Link
              href={programmePath}
              className="clients-list-view__name-link"
              onClick={() => setActiveProgrammeId(record.id)}
            >
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
        render: (status: Programme["status"]) => {
          const { label, pillClass, dotClass } =
            getProgrammeStatusConfig(status);
          return (
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {label}
            </span>
          );
        },
      },
      {
        title: "Projects",
        key: "projectCount",
        width: 120,
        align: "center",
        render: (_, record) =>
          record.projectCount ?? record.projects?.length ?? 0,
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
    [onEdit, onDelete, clientName, canEdit, canDelete],
  );

  return (
    <div className="clients-list-view">
      <AITable<Programme>
        rowKey="id"
        columns={columns}
        datasource={programmes}
        pageSize={10}
      />
    </div>
  );
}
