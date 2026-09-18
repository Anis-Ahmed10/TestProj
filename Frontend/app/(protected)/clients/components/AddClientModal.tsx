"use client";

import React, { useRef, useState } from "react";
import { CloseOutlined } from "@ant-design/icons";
import { Select, Spin, App } from "antd";
import { createClient } from "@/services/clientsService";
import { useAppSelector } from "@/store/store";
import {
  CLIENT_INDUSTRY_OPTIONS,
  Client,
  ClientFormErrors,
  ClientFormValues,
  IndustryType,
} from "@/types/client";
import {
  buildClientFieldErrors,
  getEmptyClientFormValues,
  getFriendlyClientBackendErrorMessage,
  isClientServiceError,
} from "@/utils/clients/clientsHelpers";

const { Option } = Select;

interface AddClientModalProps {
  onClose: () => void;
  onAdd: (client: Client) => void;
}

export default function AddClientModal({
  onClose,
  onAdd,
}: AddClientModalProps) {
  const user = useAppSelector((state) => state.auth?.user);
  const { message } = App.useApp();
  const locationInputRef = useRef<HTMLInputElement>(null);
  const contactInputRef = useRef<HTMLInputElement>(null);

  const [errors, setErrors] = useState<ClientFormErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [form, setForm] = useState<ClientFormValues>(() =>
    getEmptyClientFormValues(),
  );

  function handleTextChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));

    if (error) {
      setError(null);
    }

    if (errors[name as keyof typeof errors]) {
      setErrors((prev) => ({
        ...prev,
        [name]: undefined,
      }));
    }
  }

  function handleIndustryChange(value: IndustryType) {
    setForm((prev) => ({
      ...prev,
      industry: value,
    }));

    if (error) {
      setError(null);
    }
  }

  function handleFieldKeyDown(
    e: React.KeyboardEvent<HTMLInputElement>,
    nextField: (() => void) | null,
  ) {
    if (e.key !== "Enter") {
      return;
    }

    e.preventDefault();

    if (nextField) {
      nextField();
      return;
    }

    handleSubmit();
  }

  function validateForm() {
    const nextErrors: ClientFormErrors = {};

    if (!form.name.trim()) {
      nextErrors.name = "Required*";
    }

    if (!form.location.trim()) {
      nextErrors.location = "Required*";
    }

    const emailValue = form.contact.trim();
    if (!emailValue) {
      nextErrors.contact = "Required*";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
      nextErrors.contact = "Enter a valid email address.";
    }

    return nextErrors;
  }

  function handleClose() {
    if (!isSubmitting) {
      onClose();
    }
  }

  async function handleSubmit() {
    const validationErrors = validateForm();

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const createdClient = await createClient(form);
      onAdd(createdClient);
      message.success("Client created successfully.");
      onClose();
    } catch (error) {
      if (isClientServiceError(error)) {
        const fieldErrors = error.fieldErrors ?? buildClientFieldErrors(null);

        if (fieldErrors) {
          setErrors(fieldErrors);
          return;
        }

        setError(error.message);
        return;
      }

      setError(
        error instanceof Error
          ? error.message
          : getFriendlyClientBackendErrorMessage(null, null, "create"),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal_header">
          <h2 className="modal_title">Add New Client</h2>

          {!isSubmitting && (
            <button className="modal_close-btn" onClick={handleClose}>
              <CloseOutlined />
            </button>
          )}
        </div>

        <div className="modal_body">
          {error && <div className="modal_error">{error}</div>}

          <div className="modal_field">
            <label className="modal_label modal_label--inline">
              <span>Client Name *</span>
              {errors.name && (
                <span className="modal_error-text">{errors.name}</span>
              )}
            </label>

            <input
              className={
                "modal_input" + (errors.name ? " modal_input--error" : "")
              }
              name="name"
              value={form.name}
              onChange={handleTextChange}
              onKeyDown={(e) =>
                handleFieldKeyDown(e, () => locationInputRef.current?.focus())
              }
              placeholder="e.g. Lloyds Banking Group"
            />
          </div>

          <div className="modal_field-row">
            <div className="modal_field">
              <label className="modal_label">Industry *</label>

              <Select
                value={form.industry}
                onChange={handleIndustryChange}
                className="modal_select"
              >
                {CLIENT_INDUSTRY_OPTIONS.map((ind) => (
                  <Option key={ind} value={ind}>
                    {ind}
                  </Option>
                ))}
              </Select>
            </div>

            <div className="modal_field">
              <label className="modal_label modal_label--inline">
                <span>Location *</span>
                {errors.location && (
                  <span className="modal_error-text">{errors.location}</span>
                )}
              </label>

              <input
                className={
                  "modal_input" + (errors.location ? " modal_input--error" : "")
                }
                name="location"
                value={form.location}
                onChange={handleTextChange}
                ref={locationInputRef}
                onKeyDown={(e) =>
                  handleFieldKeyDown(e, () => contactInputRef.current?.focus())
                }
                placeholder="e.g. London"
              />
            </div>
          </div>

          <div className="modal_field">
            <label className="modal_label modal_label--inline">
              <span>Contact *</span>
              {errors.contact && (
                <span className="modal_error-text">{errors.contact}</span>
              )}
            </label>

            <input
              className={
                "modal_input" + (errors.contact ? " modal_input--error" : "")
              }
              name="contact"
              type="email"
              value={form.contact}
              onChange={handleTextChange}
              ref={contactInputRef}
              onKeyDown={(e) => handleFieldKeyDown(e, null)}
              placeholder="e.g. contact@company.com"
            />

            <div className="modal_field">
              <label className="modal_label">Manager</label>
              <input
                className="modal_input"
                type="text"
                value={user?.name || ""}
                disabled
              />
            </div>
          </div>
        </div>

        <div className="modal_footer">
          {!isSubmitting && (
            <button className="modal_cancel-btn" onClick={handleClose}>
              Cancel
            </button>
          )}

          <button
            className="modal_submit-btn"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Spin
                size="small"
                style={{ color: "#ffffff" }}
                aria-label="Loading"
              />
            ) : (
              "Add Client"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
