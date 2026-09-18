"use client";

import React, { useMemo } from "react";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { Client } from "@/types/client";
import { getClientStatusClassNames } from "@/utils/clients/clientsHelpers";
import AITable from "@/components/AITable";
import ListViewActions from "@/components/ListViewActions";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

interface ClientListViewProps {
  clients: Client[];
  onEdit: (client: Client) => void;
  onDelete: (client: Client) => void;
}

export default function ClientListView({
  clients,
  onEdit,
  onDelete,
}: Readonly<ClientListViewProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.CLIENT_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.CLIENT_DELETE);

  const columns: ColumnsType<Client> = useMemo(
    () => [
      {
        title: "Client Name",
        dataIndex: "name",
        key: "name",
        ellipsis: true,
        render: (name: string) => (
          <Link
            href={`/clients/workspace?clientName=${encodeURIComponent(name)}`}
            className="clients-list-view__name-link"
          >
            {name}
          </Link>
        ),
      },
      {
        title: "Industry",
        dataIndex: "industry",
        key: "industry",
        width: 160,
      },
      {
        title: "Location",
        dataIndex: "location",
        key: "location",
        width: 160,
        ellipsis: true,
      },
      {
        title: "Manager",
        dataIndex: "manager",
        key: "manager",
        render: (manager: string) => manager || "-",
      },
      {
        title: "Status",
        dataIndex: "status",
        key: "status",
        width: 140,
        render: (status: Client["status"]) => {
          const { pill: statusClass } = getClientStatusClassNames(status);
          return (
            <span className={`status-pill ${statusClass}`}>
              <span className="status-pill__dot" />
              {status}
            </span>
          );
        },
      },
      {
        title: "Programmes",
        dataIndex: "programmesCount",
        key: "programmesCount",
        width: 110,
        align: "center",
      },
      {
        title: "Projects",
        dataIndex: "projectsCount",
        key: "projectsCount",
        width: 100,
        align: "center",
      },
      {
        title: "Active Members",
        dataIndex: "activeMembersCount",
        key: "activeMembersCount",
        width: 130,
        align: "center",
      },
      {
        title: "Last Updated",
        dataIndex: "lastModified",
        key: "lastModified",
        width: 140,
      },
      {
        title: "Actions",
        key: "actions",
        width: 150,
        render: (_, record) => (
          <ListViewActions
            name={record.name}
            onEdit={() => onEdit(record)}
            onDelete={() => onDelete(record)}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        ),
      },
    ],
    [onEdit, onDelete, canEdit, canDelete],
  );

  return (
    <div className="clients-list-view">
      <AITable<Client>
        rowKey="id"
        columns={columns}
        datasource={clients}
        pageSize={10}
      />
    </div>
  );
}
