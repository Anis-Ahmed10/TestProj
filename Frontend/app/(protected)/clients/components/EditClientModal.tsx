"use client";

import { useEffect, useState, type ChangeEvent } from "react";
import { CloseOutlined } from "@ant-design/icons";
import { Select, App } from "antd";
import { useAppSelector } from "@/store/store";
import type {
  IndustryType,
  ClientStatus,
  Client,
  EditFormErrors,
} from "@/types/client";
import { CLIENT_INDUSTRY_OPTIONS, CLIENT_STATUS_OPTIONS } from "@/types/client";

import { getClientByName, updateClientByName } from "@/services/clientsService";
import { getAssignableUsers } from "@/services/userService";

type EditClientModalProps = {
  clientName: string;
  visible: boolean;
  onClose: () => void;
  onUpdated: (updated: Client) => void;
  onDeleted: (deletedClientName: string) => void;
};

type EditFormState = {
  name: string;
  contact: string;
  industry: IndustryType;
  location: string;
  status: ClientStatus;
  manager_id: string;
};

function onlyChangedPatchBody(
  original: EditFormState,
  current: EditFormState,
): Partial<{
  name: string;
  contact: string;
  industry: IndustryType;
  location: string;
  status: ClientStatus;
  manager_id: string;
}> {
  const patch: Record<string, unknown> = {};

  if (current.name.trim() && current.name.trim() !== original.name) {
    patch.name = current.name.trim();
  }
  if (current.contact.trim() && current.contact.trim() !== original.contact) {
    patch.contact = current.contact.trim();
  }
  if (current.industry !== original.industry) {
    patch.industry = current.industry;
  }
  if (
    current.location.trim() &&
    current.location.trim() !== original.location
  ) {
    patch.location = current.location.trim();
  }
  if (current.status !== original.status) {
    patch.status = current.status;
  }
  if (current.manager_id !== original.manager_id) {
    patch.manager_id = current.manager_id || null;
  }

  return patch;
}

export default function EditClientModal({
  clientName,
  visible,
  onClose,
  onUpdated,
}: Readonly<EditClientModalProps>) {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<EditFormErrors>({});
  const authState = useAppSelector(
    (state) => (state.auth as unknown as Record<string, unknown>) || {},
  );
  const [managerOptions, setManagerOptions] = useState<
    { value: string; label: string }[]
  >([]);

  const [original, setOriginal] = useState<EditFormState | null>(null);
  const [form, setForm] = useState<EditFormState>({
    name: "",
    contact: "",
    industry: "Banking",
    location: "",
    status: "On Track",
    manager_id: "",
  });

  useEffect(() => {
    if (!visible) return;

    async function loadManagers() {
      try {
        // Service call abstraction using cached user directory
        const userList = await getAssignableUsers();

        // Filter for users with a Manager or Test Manager role
        const managerUsers = userList.filter(
          (u) => !u.role || String(u.role).toLowerCase().includes("manager"),
        );

        // Merge fetched options while preserving current manager pre-selection
        setManagerOptions((prevOptions) => {
          const optionMap = new Map<string, string>();

          // Keep existing pre-selected manager
          prevOptions.forEach((opt) => optionMap.set(opt.value, opt.label));
          // Add users retrieved from service
          managerUsers.forEach((opt) => optionMap.set(opt.value, opt.label));

          return Array.from(optionMap.entries()).map(([value, label]) => ({
            value,
            label,
          }));
        });
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load user directory.",
        );
      }
    }

    loadManagers();
  }, [visible]);

  function handleTextChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;

    setForm((prev) => ({ ...prev, [name]: value }));

    if (errors[name as keyof EditFormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  }

  function validateForm() {
    const nextErrors: EditFormErrors = {};

    if (!form.name.trim()) {
      nextErrors.name = "Field cannot be empty";
    }

    if (!form.location.trim()) {
      nextErrors.location = "Field cannot be empty";
    }

    const emailValue = form.contact.trim();
    if (!emailValue) {
      nextErrors.contact = "Field cannot be empty";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
      nextErrors.contact = "Enter a valid email address.";
    }

    return nextErrors;
  }

  useEffect(() => {
    if (!visible) return;

    requestAnimationFrame(() => {
      setLoading(true);
      setOriginal(null);
      setError(null);
      setErrors({});
    });

    (async () => {
      try {
        const client = await getClientByName(clientName);
        const rawClient = client as unknown as Record<string, unknown>;

        const currentManagerName = String(
          rawClient.manager_name ?? rawClient.manager ?? "",
        );
        const currentManagerId = String(
          rawClient.manager_id ?? rawClient.manager ?? currentManagerName,
        );

        if (currentManagerName) {
          setManagerOptions((prev) => {
            const exists = prev.some(
              (opt) =>
                opt.value === currentManagerId ||
                opt.label === currentManagerName,
            );
            if (!exists) {
              return [
                {
                  value: currentManagerId || currentManagerName,
                  label: currentManagerName,
                },
                ...prev,
              ];
            }
            return prev;
          });
        }

        const selectedValue = currentManagerId || currentManagerName;

        const nextOriginal: EditFormState = {
          name: client.name,
          contact: (client as unknown as { contact?: string }).contact ?? "",
          industry: client.industry,
          location: client.location,
          status: client.status,
          manager_id: selectedValue,
        };

        setOriginal(nextOriginal);
        setForm(nextOriginal);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load client.");
      } finally {
        setLoading(false);
      }
    })();
  }, [visible, clientName]);

  function close() {
    if (saving) return;
    onClose();
  }

  function focusNextField(current: HTMLElement) {
    const focusable = Array.from(
      current
        .closest(".modal")
        ?.querySelectorAll<HTMLElement>(
          'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
    ).filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);

    const idx = focusable.indexOf(current);
    const next = focusable[idx + 1];
    if (next) next.focus();
  }

  async function handleSave() {
    if (!original) return;

    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    const patchBody = onlyChangedPatchBody(original, form);
    if (Object.keys(patchBody).length === 0) {
      setErrors({});
      onClose();
      return;
    }

    setErrors({});
    setSaving(true);
    setError(null);

    try {
      const updated = await updateClientByName(clientName, patchBody);
      const selectedManagerOption = managerOptions.find(
        (opt) => opt.value === String(form.manager_id),
      );
      const updatedClientWithManagerName: Client = {
        ...updated,
        manager: selectedManagerOption?.label || updated.manager,
      };
      onUpdated(updatedClientWithManagerName);
      message.success("Client update completed successfully.");
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update client.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal_header">
          <h2 className="modal_title">Edit Client</h2>

          <button className="modal_close-btn" onClick={close}>
            <CloseOutlined />
          </button>
        </div>

        <div className="modal_body">
          {loading ? (
            <div className="modal_loading">Loading…</div>
          ) : (
            <>
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
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.preventDefault();
                    focusNextField(e.currentTarget);
                  }}
                />
              </div>

              <div className="modal_field">
                <label className="modal_label">Contact *</label>
                <input
                  className={
                    "modal_input" +
                    (errors.contact ? " modal_input--error" : "")
                  }
                  name="contact"
                  type="email"
                  value={form.contact}
                  onChange={handleTextChange}
                  placeholder="e.g. contact@company.com"
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.preventDefault();
                    focusNextField(e.currentTarget);
                  }}
                />
              </div>

              <div className="modal_field-row">
                <div className="modal_field">
                  <label className="modal_label">Industry *</label>
                  <Select
                    value={form.industry}
                    onChange={(value) => {
                      setForm((prev) => ({ ...prev, industry: value }));
                    }}
                    style={{ width: "100%" }}
                    options={CLIENT_INDUSTRY_OPTIONS.map((ind) => ({
                      value: ind,
                      label: ind,
                    }))}
                  />
                </div>

                <div className="modal_field">
                  <label className="modal_label modal_label--inline">
                    <span>Location *</span>
                    {errors.location && (
                      <span className="modal_error-text">
                        {errors.location}
                      </span>
                    )}
                  </label>
                  <input
                    className={
                      "modal_input" +
                      (errors.location ? " modal_input--error" : "")
                    }
                    name="location"
                    value={form.location}
                    onChange={handleTextChange}
                    onKeyDown={(e) => {
                      if (e.key !== "Enter") return;
                      e.preventDefault();
                      focusNextField(e.currentTarget);
                    }}
                  />
                </div>
              </div>

              <div className="modal_field">
                <label className="modal_label">Status</label>
                <Select
                  value={form.status}
                  onChange={(value) => {
                    setForm((prev) => ({ ...prev, status: value }));
                  }}
                  style={{ width: "100%" }}
                  options={CLIENT_STATUS_OPTIONS.map((s) => ({
                    value: s,
                    label: s,
                  }))}
                />
              </div>

              <div className="modal_field">
                <label className="modal_label">Manager</label>
                <Select
                  value={form.manager_id || undefined}
                  onChange={(value) => {
                    setForm((prev) => ({ ...prev, manager_id: value ?? "" }));
                  }}
                  placeholder="Select a Manager"
                  style={{ width: "100%" }}
                  options={managerOptions}
                  showSearch
                  optionFilterProp="label"
                  allowClear
                />
              </div>

              <div className="modal_divider" />

              <div className="edit-modal_actions">
                <div className="edit-modal_actions-spacer" />

                <button
                  className="modal_cancel-btn"
                  onClick={onClose}
                  disabled={saving}
                >
                  Cancel
                </button>

                <button
                  className="modal_submit-btn"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
