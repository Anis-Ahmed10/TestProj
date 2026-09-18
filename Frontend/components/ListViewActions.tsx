"use client";

import React from "react";
import { Button } from "antd";

interface ListViewActionsProps {
  name: string;
  onEdit: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
  canEdit?: boolean;
  canDelete?: boolean;
}

export default function ListViewActions({
  name,
  onEdit,
  onDelete,
  canEdit = true,
  canDelete = true,
}: Readonly<ListViewActionsProps>) {
  return (
    <div className="clients-list-view__col--actions">
      {canEdit && (
        <Button
          className="client-card__action-btn client-card__action-btn--edit"
          size="small"
          onClick={onEdit}
          aria-label={`Edit ${name}`}
        >
          Edit
        </Button>
      )}
      {canDelete && (
        <Button
          className="client-card__action-btn client-card__action-btn--delete"
          size="small"
          onClick={onDelete}
          aria-label={`Delete ${name}`}
        >
          Delete
        </Button>
      )}
    </div>
  );
}
