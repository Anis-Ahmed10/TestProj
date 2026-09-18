"use client";

import React, { useEffect, useState } from "react";
import { Select, App, Modal, Input, Alert, Button } from "antd";
import { Client } from "@/types/client";
import { Programme } from "@/types/programme";
import {
  BackendProject,
  PROJECT_STATUS_OPTIONS,
  ProjectFormValues,
} from "@/types/project";
import { fetchClients } from "@/services/clientsService";
import { listProgrammesByClientId } from "@/services/programmeService";
import { createProject } from "@/services/projectService";
import { validateProjectForm } from "@/utils/projects/projectHelpers";
import { STATUS_LABELS } from "@/constants/status";

const { Option } = Select;
const { TextArea } = Input;

interface CreateProjectModalProps {
  existingNames: string[];
  onClose: () => void;
  onProjectCreated: (project: BackendProject) => void;
}

function getEmptyForm(): ProjectFormValues {
  return { name: "", description: "", status: "active" };
}

export default function CreateProjectModal({
  existingNames,
  onClose,
  onProjectCreated,
}: CreateProjectModalProps) {
  const { message } = App.useApp();

  const [clients, setClients] = useState<Client[]>([]);
  const [loadingClients, setLoadingClients] = useState(true);

  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [loadingProgrammes, setLoadingProgrammes] = useState(false);
  const [selectedProgrammeId, setSelectedProgrammeId] = useState<string | null>(
    null,
  );

  const [form, setForm] = useState<ProjectFormValues>(getEmptyForm());
  const [errors, setErrors] = useState<{
    client?: string;
    programme?: string;
    name?: string;
    description?: string;
    status?: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await fetchClients();
        if (active) setClients(data);
      } catch (err) {
        if (active) {
          setApiError(
            err instanceof Error ? err.message : "Failed to load clients.",
          );
        }
      } finally {
        if (active) setLoadingClients(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function handleClientChange(clientId: string) {
    setSelectedClientId(clientId);
    setSelectedProgrammeId(null);
    setProgrammes([]);
    setErrors((prev) => ({ ...prev, client: undefined, programme: undefined }));
    setApiError(null);

    setLoadingProgrammes(true);
    listProgrammesByClientId(clientId)
      .then((data) => setProgrammes(data))
      .catch((err) => {
        setApiError(
          err instanceof Error ? err.message : "Failed to load programmes.",
        );
      })
      .finally(() => setLoadingProgrammes(false));
  }

  function handleProgrammeChange(programmeId: string) {
    setSelectedProgrammeId(programmeId);
    setErrors((prev) => ({ ...prev, programme: undefined }));
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
    const validationErrors: typeof errors = validateProjectForm(form);
    if (!selectedClientId) validationErrors.client = "Please select a client.";
    if (!selectedProgrammeId)
      validationErrors.programme = "Please select a programme.";

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

    const client = clients.find((c) => c.id === selectedClientId);
    const programme = programmes.find((p) => p.id === selectedProgrammeId);

    setSubmitting(true);
    setApiError(null);

    try {
      const project = await createProject(selectedProgrammeId as string, form);
      message.success(`Project "${project.name}" created successfully.`);
      onClose();
      onProjectCreated({
        id: project.id,
        name: project.name,
        programme_id: selectedProgrammeId as string,
        programme_name: programme?.name ?? "",
        client_id: selectedClientId as string,
        client_name: client?.name ?? "",
        description: project.description,
        status: project.status,
        start_date: project.startDate,
      });
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
      title="New Project"
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

      {/* Client */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="new-proj-client"
        >
          <span>
            Client <span className="modal_required">*</span>
          </span>
          {errors.client && (
            <span className="modal_error-text">{errors.client}</span>
          )}
        </label>
        <Select
          id="new-proj-client"
          className={`modal_select${
            errors.client ? " modal_select--error" : ""
          }`}
          placeholder="Select a client"
          value={selectedClientId ?? undefined}
          onChange={handleClientChange}
          loading={loadingClients}
          disabled={submitting}
          showSearch
          optionFilterProp="children"
          aria-label="Select client"
        >
          {clients.map((c) => (
            <Option key={c.id} value={c.id}>
              {c.name}
            </Option>
          ))}
        </Select>
      </div>

      {/* Programme */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="new-proj-programme"
        >
          <span>
            Programme <span className="modal_required">*</span>
          </span>
          {errors.programme && (
            <span className="modal_error-text">{errors.programme}</span>
          )}
        </label>
        <Select
          id="new-proj-programme"
          className={`modal_select${
            errors.programme ? " modal_select--error" : ""
          }`}
          placeholder={
            selectedClientId ? "Select a programme" : "Select a client first"
          }
          value={selectedProgrammeId ?? undefined}
          onChange={handleProgrammeChange}
          loading={loadingProgrammes}
          disabled={submitting || !selectedClientId}
          showSearch
          optionFilterProp="children"
          aria-label="Select programme"
        >
          {programmes.map((p) => (
            <Option key={p.id} value={p.id}>
              {p.name}
            </Option>
          ))}
        </Select>
      </div>

      {/* Project Name */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="new-proj-name"
        >
          <span>
            Project Name <span className="modal_required">*</span>
          </span>
          {errors.name && (
            <span className="modal_error-text">{errors.name}</span>
          )}
        </label>
        <Input
          id="new-proj-name"
          name="name"
          className={`modal_input${errors.name ? " modal_input--error" : ""}`}
          value={form.name}
          onChange={(e) =>
            handleTextChange(e as React.ChangeEvent<HTMLInputElement>)
          }
          placeholder="e.g. Regression Suite Q4"
          maxLength={100}
          disabled={submitting}
          status={errors.name ? "error" : undefined}
        />
      </div>

      {/* Description */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="new-proj-description"
        >
          <span>Description</span>
          {errors.description && (
            <span className="modal_error-text">{errors.description}</span>
          )}
        </label>
        <TextArea
          id="new-proj-description"
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

      {/* Status */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="new-proj-status"
        >
          <span>
            Status <span className="modal_required">*</span>
          </span>
          {errors.status && (
            <span className="modal_error-text">{errors.status}</span>
          )}
        </label>
        <Select
          id="new-proj-status"
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
    </Modal>
  );
}
