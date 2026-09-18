"use client";

import React, { useState, useMemo } from "react";
import { Button, Input, Modal, Alert } from "antd";
import { Project } from "@/types/project";
import { deleteProjectById } from "@/services/projectService";

interface DeleteProjectPopupProps {
  project: Project;
  onClose: () => void;
  onDeleted: (deletedId: string) => void;
}

export default function DeleteProjectPopup({
  project,
  onClose,
  onDeleted,
}: DeleteProjectPopupProps) {
  const [deleteInput, setDeleteInput] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isDeleteAllowed = useMemo(
    () => deleteInput === "delete",
    [deleteInput],
  );

  async function handleConfirmDelete() {
    if (!isDeleteAllowed || deleting) return;
    setDeleting(true);
    setApiError(null);
    try {
      await deleteProjectById(project.id);
      onDeleted(project.id);
    } catch (err) {
      setApiError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Modal
      open
      title="Delete Project"
      onCancel={deleting ? undefined : onClose}
      closable={!deleting}
      mask={{ closable: !deleting }}
      footer={[
        <Button key="cancel" onClick={onClose} disabled={deleting}>
          Cancel
        </Button>,
        <Button
          key="delete"
          danger
          type="primary"
          onClick={handleConfirmDelete}
          disabled={!isDeleteAllowed || deleting}
          loading={deleting}
        >
          Confirm Delete
        </Button>,
      ]}
    >
      {apiError && (
        <Alert
          type="error"
          title={apiError}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <div className="edit-modal__delete-confirm" style={{ marginTop: 4 }}>
        <div className="edit-modal__delete-warning">
          Deleting <strong>{project.name}</strong> will permanently remove this
          project and cannot be undone.
        </div>

        <label className="modal__label">Type delete to confirm *</label>
        <Input
          value={deleteInput}
          onChange={(e) => setDeleteInput(e.target.value)}
          placeholder="delete"
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            if (!isDeleteAllowed || deleting) return;
            e.preventDefault();
            handleConfirmDelete();
          }}
          disabled={deleting}
        />
      </div>
    </Modal>
  );
}
