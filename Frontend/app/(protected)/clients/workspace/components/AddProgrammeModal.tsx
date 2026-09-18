"use client";

import React, { useRef, useState } from "react";
import { Select, Spin, Modal, Input, Alert, Button } from "antd";
import type { TextAreaRef } from "antd/es/input/TextArea";
import { createProgramme } from "@/services/programmeService";
import { Programme } from "@/types/programme";
const { Option } = Select;
const { TextArea } = Input;

interface FormValues {
  name: string;
  description: string;
}

interface FormErrors {
  name?: string;
  description?: string;
}

interface AddProgrammeModalProps {
  clientId: string;
  clientDisplayName: string;
  existingNames: string[];
  onClose: () => void;
  onAdd: (programme: Programme) => void;
}

function getEmpty(): FormValues {
  return { name: "", description: "" };
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

  const desc = values.description.trim();
  if (desc.length > 500) {
    errors.description = "Description must be 500 characters or fewer.";
  }

  return errors;
}

export default function AddProgrammeModal({
  clientId,
  clientDisplayName,
  existingNames,
  onClose,
  onAdd,
}: AddProgrammeModalProps) {
  const [form, setForm] = useState<FormValues>(getEmpty());
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const descRef = useRef<TextAreaRef>(null);

  function handleText(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
    setApiError(null);
  }

  function handleKeyDown(
    e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
    next: (() => void) | null,
  ) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (next) {
      next();
      return;
    }
    handleSubmit();
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
      const created = await createProgramme({
        clientId,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      });

      const newProgramme: Programme = {
        id: created.id,
        clientId: created.clientId,
        name: created.name,
        description: form.description.trim() || undefined,
        status: "active",
        projects: [],
      };

      onAdd(newProgramme);
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
          <div>Add Programme</div>
          <div style={{ fontSize: 13, fontWeight: 400, color: "#666" }}>
            Client: <strong>{clientDisplayName}</strong>
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
          key="submit"
          type="primary"
          onClick={handleSubmit}
          loading={submitting}
        >
          Add Programme
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
        <label className="modal_label modal_label--inline" htmlFor="prog-name">
          <span>
            Programme Name <span className="modal_required">*</span>
          </span>
          {errors.name && (
            <span className="modal_error-text">{errors.name}</span>
          )}
        </label>
        <Input
          id="prog-name"
          name="name"
          className={`modal_input${errors.name ? " modal_input--error" : ""}`}
          value={form.name}
          onChange={(e) => handleText(e as React.ChangeEvent<HTMLInputElement>)}
          onKeyDown={(e) =>
            handleKeyDown(
              e as React.KeyboardEvent<HTMLInputElement>,
              () => descRef.current?.focus(),
            )
          }
          placeholder="e.g. Payments Modernization"
          maxLength={255}
          disabled={submitting}
          autoFocus
          status={errors.name ? "error" : undefined}
        />
      </div>

      {/* Description */}
      <div className="modal_field">
        <label className="modal_label modal_label--inline" htmlFor="prog-desc">
          <span>Description</span>
          {errors.description && (
            <span className="modal_error-text">{errors.description}</span>
          )}
        </label>
        <TextArea
          id="prog-desc"
          name="description"
          ref={descRef}
          className={`modal_input modal_textarea${
            errors.description ? " modal_input--error" : ""
          }`}
          value={form.description}
          onChange={handleText}
          onKeyDown={(e) =>
            handleKeyDown(
              e as React.KeyboardEvent<HTMLTextAreaElement>,
              () => null,
            )
          }
          placeholder="Brief description of the programme (optional)"
          rows={3}
          maxLength={500}
          disabled={submitting}
          status={errors.description ? "error" : undefined}
        />
        <span className="modal_char-hint">{form.description.length}/500</span>
      </div>
    </Modal>
  );
}
