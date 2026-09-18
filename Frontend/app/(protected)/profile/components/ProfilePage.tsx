"use client";

import React, { useEffect, useState } from "react";
import { Button, Input, Tag, App } from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { usePermissions } from "@/hooks/usePermissions";
import {
  getMyJiraCredentials,
  saveMyJiraCredentials,
} from "@/services/jiraService";

interface JiraCredentialsDraft {
  jiraEmail: string;
  apiToken: string;
}

export default function ProfilePage() {
  const { message, modal } = App.useApp();
  const { user } = usePermissions();

  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [hasApiToken, setHasApiToken] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [saved, setSaved] = useState<JiraCredentialsDraft>({
    jiraEmail: "",
    apiToken: "",
  });
  const [draft, setDraft] = useState<JiraCredentialsDraft>(saved);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadFailed(false);
    getMyJiraCredentials()
      .then((credentials) => {
        if (cancelled) return;
        const next: JiraCredentialsDraft = {
          jiraEmail: credentials.jiraEmail,
          apiToken: "",
        };
        setSaved(next);
        setDraft(next);
        setHasApiToken(credentials.hasApiToken);
      })
      .catch((error) => {
        if (cancelled) return;
        console.error("Failed to load Jira credentials:", error);
        // A blank form would read as "you never saved anything", so say so
        // instead — otherwise the user re-enters a token they still have.
        setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const startEdit = () => {
    setDraft(saved);
    setIsEditing(true);
  };

  const handleCancel = () => {
    setDraft(saved);
    setIsEditing(false);
  };

  const handleSave = async () => {
    // An empty email is the backend's "clear it" signal, so saving a blank field
    // would silently wipe the stored one — clearing has its own guarded button.
    if (!draft.jiraEmail.trim()) {
      message.error(
        "Enter your Jira email, or use Remove credentials to clear them.",
      );
      return;
    }
    setSaving(true);
    try {
      const result = await saveMyJiraCredentials({
        jiraEmail: draft.jiraEmail,
        apiToken: draft.apiToken ? draft.apiToken : undefined,
      });
      const next: JiraCredentialsDraft = {
        jiraEmail: result.jiraEmail,
        apiToken: "",
      };
      setSaved(next);
      setDraft(next);
      setHasApiToken(result.hasApiToken);
      setIsEditing(false);
      message.success("Jira credentials saved.");
    } catch (error) {
      console.error("Failed to save Jira credentials:", error);
      message.error(
        error instanceof Error
          ? error.message
          : "Failed to save Jira credentials.",
      );
    } finally {
      setSaving(false);
    }
  };

  async function removeCredentials() {
    setRemoving(true);
    try {
      // Empty strings are the backend's "clear this" signal, and clearing skips
      // verification — so this works even once the token is revoked in Jira.
      await saveMyJiraCredentials({ jiraEmail: "", apiToken: "" });
      const cleared: JiraCredentialsDraft = { jiraEmail: "", apiToken: "" };
      setSaved(cleared);
      setDraft(cleared);
      setHasApiToken(false);
      setIsEditing(false);
      message.success("Jira credentials removed.");
    } catch (error) {
      console.error("Failed to remove Jira credentials:", error);
      message.error(
        error instanceof Error
          ? error.message
          : "Failed to remove Jira credentials.",
      );
    } finally {
      setRemoving(false);
    }
  }

  const handleRemove = () => {
    modal.confirm({
      title: "Remove Jira credentials?",
      content:
        "Jira pull and push will stop working until you save a new email and API token.",
      okText: "Remove",
      okButtonProps: { danger: true },
      onOk: removeCredentials,
    });
  };

  const hasSavedCredentials = hasApiToken || Boolean(saved.jiraEmail);

  const initials = user?.name
    ? user.name
        .split(/\s+/)
        .map((part) => part[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "–";

  return (
    <div className="max-w-3xl mx-auto p-6 flex flex-col gap-6">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-4 mb-6">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#1f3333] text-lg font-semibold text-white">
            {initials}
          </div>
          <div>
            <p className="text-lg font-semibold text-gray-900">
              {user?.name ?? "—"}
            </p>
            <Tag className="rounded-full px-3 py-0.5 font-semibold text-xs m-0 mt-1">
              {user?.role ?? "Unassigned"}
            </Tag>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <div className="text-xs text-gray-500 mb-1.5">Name</div>
            <Input
              value={user?.name ?? ""}
              readOnly
              className="rounded-lg! bg-gray-50! text-gray-700!"
            />
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1.5">Email</div>
            <Input
              value={user?.email ?? ""}
              readOnly
              className="rounded-lg! bg-gray-50! text-gray-700!"
            />
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1.5">Role</div>
            <Input
              value={user?.role ?? ""}
              readOnly
              className="rounded-lg! bg-gray-50! text-gray-700!"
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-5">
          <UserOutlined className="text-gray-700" />
          <span className="text-sm font-semibold text-gray-900">
            Jira Configuration
          </span>
        </div>

        {loadFailed ? (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-gray-700">
              We couldn&apos;t load your Jira settings. Any credentials you
              saved are still there — this page just couldn&apos;t read them.
            </p>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => setReloadKey((key) => key + 1)}
              loading={loading}
              className="rounded-lg!"
            >
              Try again
            </Button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-6">
              <div>
                <div className="text-xs text-gray-500 mb-1.5">Jira Email</div>
                <Input
                  value={isEditing ? draft.jiraEmail : saved.jiraEmail}
                  onChange={
                    isEditing
                      ? (e) =>
                          setDraft((d) => ({ ...d, jiraEmail: e.target.value }))
                      : undefined
                  }
                  readOnly={!isEditing}
                  placeholder="you@company.com"
                  disabled={loading}
                  className={`rounded-lg! text-gray-700 ${
                    isEditing ? "bg-white" : "bg-gray-50"
                  }`}
                />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1.5">
                  Jira API Token
                </div>
                <Input.Password
                  value={isEditing ? draft.apiToken : ""}
                  onChange={
                    isEditing
                      ? (e) =>
                          setDraft((d) => ({ ...d, apiToken: e.target.value }))
                      : undefined
                  }
                  readOnly={!isEditing}
                  placeholder={hasApiToken ? "•••••••• (saved)" : "—"}
                  disabled={loading}
                  className={`rounded-lg! ${
                    isEditing ? "bg-white" : "bg-gray-50"
                  }`}
                />
              </div>
            </div>

            <p className="text-xs text-gray-500 mb-6">
              Used to authenticate Jira pull/push operations as you. Jira
              operations are blocked until both fields are set.
            </p>

            <div className="flex gap-2">
              {isEditing ? (
                <>
                  <Button
                    onClick={handleCancel}
                    className="rounded-lg!"
                    disabled={saving}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleSave}
                    loading={saving}
                    className="bg-[#1f3333]! border-[#1f3333]! text-white! rounded-lg!"
                  >
                    Save
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    icon={<EditOutlined />}
                    onClick={startEdit}
                    className="rounded-lg!"
                    disabled={loading || removing}
                  >
                    Edit
                  </Button>
                  {hasSavedCredentials && (
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={handleRemove}
                      loading={removing}
                      className="rounded-lg!"
                      disabled={loading}
                    >
                      Remove credentials
                    </Button>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
