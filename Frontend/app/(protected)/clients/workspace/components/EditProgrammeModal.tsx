"use client";

import React, { useRef, useState } from "react";
import { Select, Modal, Input, Alert, Button } from "antd";
import { Programme } from "@/types/programme";
import { updateProgrammeById } from "@/services/programmeService";
import type { TextAreaRef } from "antd/es/input/TextArea";
const { Option } = Select;
const { TextArea } = Input;

interface FormValues {
  name: string;
  description: string;
  status: string;
}

interface FormErrors {
  name?: string;
  description?: string;
}

interface EditProgrammeModalProps {
  programme: Programme;
  existingNames: string[];
  onClose: () => void;
  onUpdated: (updated: Programme) => void;
}

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {};
  const name = values.name.trim();
  if (!name) {
    errors.name = "Required*";
  } else if (name.length > 255) {
    errors.name = "Name must be 255 characters or fewer.";
  } else if (!/^[\w\s\-.,()&'/]+$/i.test(name)) {
    errors.name = "Name contains invalid characters.";
  }
  if (values.description.trim().length > 500) {
    errors.description = "Description must be 500 characters or fewer.";
  }
  return errors;
}

export default function EditProgrammeModal({
  programme,
  existingNames,
  onClose,
  onUpdated,
}: EditProgrammeModalProps) {
  const [form, setForm] = useState<FormValues>({
    name: programme.name,
    description: programme.description ?? "",
    status: programme.status ?? "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const descRef = useRef<TextAreaRef>(null);

  function handleTextChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
    setApiError(null);
  }

  function handleStatusChange(value: string) {
    setForm((prev) => ({ ...prev, status: value }));
    setApiError(null);
  }

  async function handleSubmit() {
    const errs = validate(form);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    const trimmed = form.name.trim().toLowerCase();
    if (existingNames.some((n) => n.trim().toLowerCase() === trimmed)) {
      setApiError(
        "A programme with this name already exists. Please choose a different name.",
      );
      return;
    }

    setSubmitting(true);
    setApiError(null);

    try {
      const updated = await updateProgrammeById(programme.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        status: form.status,
      });
      onUpdated({ ...programme, ...updated });
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
          <div>Edit Programme</div>
          <div style={{ fontSize: 13, fontWeight: 400, color: "#666" }}>
            Editing: <strong>{programme.name}</strong>
          </div>
        </div>
      }
      onCancel={submitting ? undefined : onClose}
      closable={!submitting}
      mask={{ closable: !submitting }}
      footer={[
        !submitting && (
          <Button key="cancel" onClick={onClose}>
            Cancel
          </Button>
        ),
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

      {/* Name */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="edit-prog-name"
        >
          <span>
            Programme Name <span className="modal_required">*</span>
          </span>
          {errors.name && (
            <span className="modal_error-text">{errors.name}</span>
          )}
        </label>
        <Input
          id="edit-prog-name"
          name="name"
          className={`modal_input${errors.name ? " modal_input--error" : ""}`}
          value={form.name}
          onChange={(e) =>
            handleTextChange(e as React.ChangeEvent<HTMLInputElement>)
          }
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              descRef.current?.focus();
            }
          }}
          placeholder="e.g. Payments Modernization"
          maxLength={255}
          disabled={submitting}
          autoFocus
          status={errors.name ? "error" : undefined}
        />
      </div>

      {/* Description */}
      <div className="modal_field">
        <label
          className="modal_label modal_label--inline"
          htmlFor="edit-prog-desc"
        >
          <span>Description</span>
          {errors.description && (
            <span className="modal_error-text">{errors.description}</span>
          )}
        </label>
        <TextArea
          id="edit-prog-desc"
          name="description"
          ref={descRef}
          className={`modal_input modal_textarea${
            errors.description ? " modal_input--error" : ""
          }`}
          value={form.description}
          onChange={handleTextChange}
          placeholder="Brief description of the programme (optional)"
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
          htmlFor="edit-prog-status"
        >
          <span>Status</span>
        </label>
        <Select
          id="edit-prog-status"
          className="modal_select"
          value={form.status}
          onChange={handleStatusChange}
          disabled={submitting}
          aria-label="Programme status"
        >
          <Option value="active">Active</Option>
          <Option value="onhold">On Hold</Option>
          <Option value="complete">Complete</Option>
        </Select>
      </div>
    </Modal>
  );
}
