"use client";

import React from "react";
import { Button, Card, Space } from "antd";
import Link from "next/link";
import { Client } from "@/types/client";
import { getClientStatusClassNames } from "@/utils/clients/clientsHelpers";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

interface ClientCardProps {
  client: Client;
  onEdit: () => void;
  onDelete: (clientName: string) => void;
}

export default function ClientCard({
  client,
  onEdit,
  onDelete,
}: Readonly<ClientCardProps>) {
  const { hasPermission } = usePermissions();
  const canEdit = hasPermission(PERMISSIONS.CLIENT_UPDATE);
  const canDelete = hasPermission(PERMISSIONS.CLIENT_DELETE);
  const { progress: progressClass, pill: statusClass } =
    getClientStatusClassNames(client.status);

  return (
    <Link
      href={`/clients/workspace?clientName=${encodeURIComponent(client.name)}`}
      className="client-card__link"
      style={{ display: "block", textDecoration: "none", color: "inherit" }}
    >
      <Card className="client-card" style={{ cursor: "pointer" }}>
        <div className="client-card__header">
          <div className="client-card__header-left">
            <h3 className="client-card__name">{client.name}</h3>

            <span className={`status-pill ${statusClass}`}>
              <span className="status-pill__dot" />
              {client.status}
            </span>
          </div>

          <div className="client-card__actions">
            {canEdit && (
              <Button
                className="client-card__action-btn client-card__action-btn--edit"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onEdit();
                }}
                aria-label={`Edit ${client.name}`}
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
                  onDelete(client.name);
                }}
                aria-label={`Delete ${client.name}`}
              >
                Delete
              </Button>
            )}
          </div>
        </div>

        <Space size="middle" wrap>
          <span className="client-card__stat">
            <span className="client-card__stat-label">Programmes:&nbsp;</span>
            <span className="client-card__stat-value">
              {client.programmesCount}
            </span>
          </span>

          <span className="client-card__stat">
            <span className="client-card__stat-label">Projects:&nbsp;</span>
            <span className="client-card__stat-value">
              {client.projectsCount}
            </span>
          </span>

          <span className="client-card__stat">
            <span className="client-card__stat-label">
              Active Members:&nbsp;
            </span>
            <span className="client-card__stat-value">
              {client.activeMembersCount}
            </span>
          </span>
        </Space>

        <div className="client-card__progress-bar">
          <div
            className={`client-card__progress-fill ${progressClass}`}
            style={{ width: `${client.progress}%` }}
          />
        </div>

        <div className="client-card__footer">
          <span className="client-card__location">
            {client.industry}
            <span className="client-card__industry-dot" />
            {client.location}
            {client.manager && (
              <>
                <span className="client-card__industry-dot" />
                <span>
                  Manager: <strong>{client.manager}</strong>
                </span>
              </>
            )}
          </span>
          <span>{client.lastModified}</span>
        </div>
      </Card>
    </Link>
  );
}
