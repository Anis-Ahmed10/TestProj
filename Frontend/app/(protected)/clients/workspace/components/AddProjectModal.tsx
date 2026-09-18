"use client";

import React, { useState, useEffect } from "react";
import { Select, App, Modal, Input, Alert, Button } from "antd";
import {
  Project,
  PROJECT_STATUS_OPTIONS,
  ProjectFormValues,
} from "@/types/project";
import { Programme } from "@/types/programme";
import { createProject } from "@/services/projectService";
import { validateProjectForm } from "@/utils/projects/projectHelpers";
import { STATUS_LABELS } from "@/constants/status";
import { getAssignableUsers, type UserOption } from "@/services/userService";

const { Option } = Select;
const { TextArea } = Input;

interface AddProjectModalProps {
  programme: Programme;
  existingNames: string[];
  onClose: () => void;
  onProjectAdded: (project: Project) => void;
}

function getEmptyForm(): ProjectFormValues {
  return {
    name: "",
    description: "",
    status: "active",
    leadId: undefined,
  };
}

export default function AddProjectModal({
  programme,
  existingNames,
  onClose,
  onProjectAdded,
}: AddProjectModalProps) {
  const { message } = App.useApp();
  const [form, setForm] = useState<ProjectFormValues>(getEmptyForm());
  const [errors, setErrors] = useState<{
    name?: string;
    description?: string;
    status?: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [userOptions, setUserOptions] = useState<UserOption[]>([]);

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

  async function handleSubmit() {
    const validationErrors = validateProjectForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }
    const trimmed = form.name.trim().toLowerCase();
    if (existingNames.some((n) => n.trim().toLowerCase() === trimmed)) {
      setApiError(
        "A project with this name already exists. Please choose a different name.",
      );
      return;
    }

    setSubmitting(true);
    setApiError(null);

    try {
      const project = await createProject(programme.id, form);
      onProjectAdded(project);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.";
      setApiError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      title={
        <div>
          <div>Create Project</div>
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
          key="submit"
          type="primary"
          onClick={handleSubmit}
          loading={submitting}
        >
          Create Project
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
        <label className="modal_label modal_label--inline" htmlFor="proj-name">
          <span>
            Project Name <span className="modal_required">*</span>
          </span>
          {errors.name && (
            <span className="modal_error-text">{errors.name}</span>
          )}
        </label>
        <Input
          id="proj-name"
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
          htmlFor="proj-description"
        >
          <span>Description</span>
          {errors.description && (
            <span className="modal_error-text">{errors.description}</span>
          )}
        </label>
        <TextArea
          id="proj-description"
          name="description"
          className={`modal_input modal_textarea${
            errors.description ? " modal_input--error" : ""
          }`}
          value={form.description}
          onChange={handleTextChange}
          placeholder="Brief description of the project (optional)"
          rows={3}
          maxLength={500}
          disabled={submitting}
          status={errors.description ? "error" : undefined}
        />
        <span className="modal_char-hint">{form.description.length}/500</span>
      </div>

      {/* ── Status & Project Lead side-by-side ── */}
      <div style={{ display: "flex", gap: 16 }}>
        {/* Status */}
        <div className="modal_field" style={{ flex: 1 }}>
          <label
            className="modal_label modal_label--inline"
            htmlFor="proj-status"
          >
            <span>
              Status <span className="modal_required">*</span>
            </span>
            {errors.status && (
              <span className="modal_error-text">{errors.status}</span>
            )}
          </label>
          <Select
            id="proj-status"
            className={`modal_select${
              errors.status ? " modal_select--error" : ""
            }`}
            style={{ width: "100%" }}
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

        {/* Project Lead / Manager */}
        <div className="modal_field" style={{ flex: 1 }}>
          <label className="modal_label" htmlFor="create-proj-lead">
            <span>
              Project Lead / Manager <span className="modal_required">*</span>
            </span>
          </label>
          <Select
            id="create-proj-lead"
            showSearch
            allowClear
            className="modal_select"
            style={{ width: "100%" }}
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
