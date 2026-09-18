"use client";

import React, { useEffect, useMemo, useState } from "react";
import { CloseOutlined } from "@ant-design/icons";
import { Alert, Button, Input, App } from "antd";
import type { Client } from "@/types/client";
import { deleteClientByName } from "@/services/clientsService";

type DeleteClientPopupProps = {
  client: Client;
  onClose: () => void;
  onDeleted: (deletedClientName: string) => void;
};

export default function DeleteClientPopup({
  client,
  onClose,
  onDeleted,
}: Readonly<DeleteClientPopupProps>) {
  const { message } = App.useApp();
  const [deleteInput, setDeleteInput] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDeleteAllowed = useMemo(
    () => deleteInput === "delete",
    [deleteInput],
  );

  useEffect(() => {
    if (deleteInput === "" && deleting === false && error === null) return;
    setDeleteInput("");
    setDeleting(false);
    setError(null);
  }, [client.name]);

  function close() {
    if (deleting) return;
    onClose();
  }

  async function handleDelete() {
    if (!isDeleteAllowed || deleting) return;
    setDeleting(true);
    setError(null);

    try {
      await deleteClientByName(client.name);
      message.success("Client deleted successfully.");
      onDeleted(client.name);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete client.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h2 className="modal__title">Delete Client</h2>
          <Button
            className="modal__close-btn"
            onClick={close}
            type="text"
            aria-label="Close"
            icon={<CloseOutlined />}
            disabled={deleting}
          />
        </div>

        <div className="modal__body">
          {error && (
            <Alert
              type="error"
              title={error}
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <div className="edit-modal__delete-confirm" style={{ marginTop: 4 }}>
            <div className="edit-modal__delete-warning">
              Deleting <strong>{client.name}</strong> will permanently archive
              this client. Clients with active projects cannot be deleted —
              archive or complete all projects first.
            </div>

            <label className="modal__label">Type delete to confirm *</label>
            <Input
              className="modal__input"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              placeholder="delete"
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                if (!isDeleteAllowed || deleting) return;
                e.preventDefault();
                handleDelete();
              }}
              disabled={deleting}
            />

            <div className="edit-modal__delete-confirm-actions">
              <Button
                className="modal__cancel-btn"
                onClick={onClose}
                disabled={deleting}
              >
                Cancel
              </Button>

              <Button
                className="edit-modal__confirm-delete-btn"
                onClick={handleDelete}
                disabled={!isDeleteAllowed || deleting}
                loading={deleting}
              >
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
