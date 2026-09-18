"use client";

import React, { useEffect, useState } from "react";
import { CloseOutlined, LoadingOutlined } from "@ant-design/icons";
import { PlatformUser, PlatformRole } from "@/types/user";
import { updateUserRole } from "@/services/userService";

interface EditUserRoleModalProps {
  user: PlatformUser;
  roles: PlatformRole[];
  onClose: () => void;
  onUpdated: (updatedUser: PlatformUser) => void;
}

export default function EditUserRoleModal({
  user,
  roles,
  onClose,
  onUpdated,
}: EditUserRoleModalProps) {
  const initialRole = roles.some((r) => r.name === user.role)
    ? user.role ?? ""
    : roles[0]?.name ?? "";
  const [selectedRole, setSelectedRole] = useState(initialRole);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!roles.some((r) => r.name === selectedRole)) {
      const validRole = roles.some((r) => r.name === user.role)
        ? user.role ?? ""
        : roles[0]?.name ?? "";
      if (validRole !== selectedRole) {
        setSelectedRole(validRole);
      }
    }
  }, [roles, user.role, selectedRole]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSubmitting, onClose]);

  async function handleSave() {
    if (!selectedRole || selectedRole === (user.role ?? "")) {
      onClose();
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await updateUserRole(user.id, selectedRole);
      onUpdated({ ...user, role: selectedRole });
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update role. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleOverlayClick() {
    if (!isSubmitting) {
      onClose();
    }
  }

  return (
    <div
      className="um-modal-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-role-modal-title"
    >
      <div className="um-modal" onClick={(e) => e.stopPropagation()}>
        <div className="um-modal__header">
          <h2 className="um-modal__title" id="edit-role-modal-title">
            Edit User Role
          </h2>
          {!isSubmitting && (
            <button
              className="um-modal__close-btn"
              onClick={onClose}
              aria-label="Close dialog"
            >
              <CloseOutlined />
            </button>
          )}
        </div>

        <div className="um-modal__body">
          {error && <div className="um-modal__error">{error}</div>}
          <div className="um-modal__user-info">
            <div>
              <p className="um-modal__user-name">{user.name ?? "Unnamed"}</p>
              <p className="um-modal__user-email">{user.email ?? ""}</p>
            </div>
          </div>

          <div className="um-modal__field">
            <label className="um-modal__label">Current Role</label>
            <div className="um-modal__current-role">
              {user.role || "Unassigned"}
            </div>
          </div>

          <div className="um-modal__field">
            <label className="um-modal__label" htmlFor="role-select">
              Assign New Role
            </label>
            <select
              id="role-select"
              className="um-modal__select"
              value={selectedRole}
              onChange={(e) => {
                setSelectedRole(e.target.value);
                setError(null);
              }}
              disabled={isSubmitting}
            >
              {roles.map((r) => (
                <option key={r.id} value={r.name}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="um-modal__footer">
          {!isSubmitting && (
            <button
              className="um-modal__cancel-btn"
              onClick={onClose}
              id="edit-role-cancel-btn"
            >
              Cancel
            </button>
          )}
          <button
            className="um-modal__save-btn"
            onClick={handleSave}
            disabled={isSubmitting || !selectedRole}
            id="edit-role-save-btn"
          >
            {isSubmitting ? (
              <>
                <LoadingOutlined spin />
                Saving…
              </>
            ) : (
              "Save"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
