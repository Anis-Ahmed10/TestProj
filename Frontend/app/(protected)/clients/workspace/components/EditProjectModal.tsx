"use client";

import React, { useEffect, useState } from "react";
import { Select, Modal, Input, Alert, Button } from "antd";
import {
  Project,
  PROJECT_STATUS_OPTIONS,
  ProjectFormValues,
} from "@/types/project";
import { Programme } from "@/types/programme";
import { STATUS_LABELS } from "@/constants/status";
import { updateProjectById } from "@/services/projectService";
import { getAssignableUsers, type UserOption } from "@/services/userService";

const { Option } = Select;
const { TextArea } = Input;

interface EditProjectModalProps {
  project: Project;
  programme: Programme;
  existingNames: string[];
  onClose: () => void;
  onUpdated: (updated: Project) => void;
}

export default function EditProjectModal({
  project,
  programme,
  existingNames,
  onClose,
  onUpdated,
}: EditProjectModalProps) {
  const [form, setForm] = useState<ProjectFormValues>({
    name: project.name,
    description: project.description ?? "",
    status: project.status,
    leadId: project.leadId ?? undefined,
  });
  const [userOptions, setUserOptions] = useState<UserOption[]>([]);
  const [errors, setErrors] = useState<{
    name?: string;
    status?: string;
    startDate?: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    getAssignableUsers()
      .then((users) => {
        const filtered = users.filter((u) => {
          const roleStr = String(u.role ?? "").toLowerCase();
          return roleStr.includes("lead") || roleStr.includes("manager");
        });
        setUserOptions(filtered);
      })
      .catch((err) => {
        setUserOptions([]);
        setApiError(
          err instanceof Error ? err.message : "Could not load the user list.",
        );
      });
  }, []);

  function handleLeadChange(value: string) {
    setForm((prev) => ({
      ...prev,
      leadId: value || undefined,
    }));
    setApiError(null);
  }

  function handleTextChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof typeof errors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
    setApiError(null);
  }

  function handleStatusChange(value: string) {
    setForm((prev) => ({
      ...prev,
      status: value as ProjectFormValues["status"],
    }));
    if (errors.status) setErrors((prev) => ({ ...prev, status: undefined }));
    setApiError(null);
  }

  function validateForm(): boolean {
    const errs: { name?: string; status?: string } = {};
    if (!form.name.trim()) errs.name = "Required*";
    else if (form.name.trim().length > 50)
      errs.name = "Name must be 50 characters or fewer.";
    if (!form.status) errs.status = "Required*";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    const valid = validateForm();
    if (!valid) return;

    const trimmedName = form.name.trim().toLowerCase();
    if (
      trimmedName !== project.name.trim().toLowerCase() &&
      existingNames.some((n) => n.trim().toLowerCase() === trimmedName)
    ) {
      setApiError(
        "A project with this name already exists. Please choose a different name.",
      );
      return;
    }

    setSubmitting(true);
    setApiError(null);
    try {
      const updated = await updateProjectById(project.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        status: form.status,
        lead_id: form.leadId || null,
      });
      onUpdated(updated);
    } catch (err) {
      setApiError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      title={
        <div>
          <div>Edit Project</div>
          <div style={{ fontSize: 13, fontWeight: 400, color: "#666" }}>
            Under: <strong>{programme.name}</strong>
          </div>
        </div>
      }
      onCancel={submitting ? undefined : onClose}
      closable={!submitting}
      mask={{ closable: !submitting }}
      footer={[
        <Button key="cancel" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={handleSubmit}
          loading={submitting}
        >
          Save Changes
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

      {/* Project Name */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="edit-proj-name"
        >
          <span>
            Project Name <span className="modal_required">*</span>
          </span>
          {errors.name && (
            <span className="modal_error-text">{errors.name}</span>
          )}
        </label>
        <Input
          id="edit-proj-name"
          name="name"
          className={`modal_input${errors.name ? " modal_input--error" : ""}`}
          value={form.name}
          onChange={(e) =>
            handleTextChange(e as React.ChangeEvent<HTMLInputElement>)
          }
          placeholder="e.g. Regression Suite Q4"
          maxLength={100}
          disabled={submitting}
          autoFocus
          status={errors.name ? "error" : undefined}
        />
      </div>

      {/* Description */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="edit-proj-description"
        >
          <span>Description</span>
        </label>
        <TextArea
          id="edit-proj-description"
          name="description"
          className="modal_input modal_textarea"
          value={form.description}
          onChange={handleTextChange}
          placeholder="Brief description of the project (optional)"
          rows={3}
          maxLength={500}
          disabled={submitting}
        />
        <span className="modal_char-hint">{form.description.length}/500</span>
      </div>

      {/* Start Date + Status + Manager / Lead Field*/}
      <div className="modal_field-row">
        <div className="modal_field">
          <label
            className="modal_label modal_label--inline"
            htmlFor="edit-proj-status"
          >
            <span>
              Status <span className="modal_required">*</span>
            </span>
            {errors.status && (
              <span className="modal_error-text">{errors.status}</span>
            )}
          </label>
          <Select
            id="edit-proj-status"
            className={`modal_select${
              errors.status ? " modal_select--error" : ""
            }`}
            value={form.status}
            onChange={handleStatusChange}
            disabled={submitting}
            aria-label="Project status"
          >
            {PROJECT_STATUS_OPTIONS.map((s) => (
              <Option key={s} value={s}>
                {STATUS_LABELS[s]}
              </Option>
            ))}
          </Select>
        </div>
        {/* Manager / Lead Field */}
        <div className="modal_field">
          <label className="modal_label" htmlFor="edit-proj-lead">
            <span>Project Lead / Manager</span>
          </label>
          <Select
            id="edit-proj-lead"
            showSearch
            allowClear
            className="modal_select"
            value={form.leadId}
            onChange={handleLeadChange}
            placeholder="Search and select Lead or Manager"
            options={userOptions}
            optionFilterProp="label"
            disabled={submitting}
          />
        </div>
      </div>
    </Modal>
  );
}
