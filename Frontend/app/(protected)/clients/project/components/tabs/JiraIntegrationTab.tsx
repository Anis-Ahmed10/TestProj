"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Button, Input, Tag, Table, Empty, Modal, App } from "antd";
import { EditOutlined, SyncOutlined } from "@ant-design/icons";
import JiraDiamondIcon from "../../assets/icons/JiraDiamondIcon";
import {
  getJiraConfig,
  saveJiraConfig,
  testJiraConnection,
} from "@/services/jiraService";
import { fetchApplicationLogs } from "@/services/applicationlogsservice";

interface SyncHistoryRow {
  key: string;
  date: string;
  direction: string;
  items: string;
  status: number | null;
  details: string;
}

const SYNC_HISTORY_COOLDOWN_MS = 60_000; // 1 min
const syncHistoryCache = new Map<
  string,
  { rows: SyncHistoryRow[]; fetchedAt: number }
>();

const SYNC_ENDPOINT_PATTERN =
  /\/jira\/(push-to-jira|fetch-issues|refresh-imported-stories|apply-refresh-changes)/;

function parseSyncMessage(message: string | null): {
  direction: string;
  items: string;
  details: string;
} {
  const result = { direction: "—", items: "—", details: message ?? "" };
  if (!message) return result;
  message.split("|").forEach((part) => {
    const [key, ...rest] = part.split(":");
    const value = rest.join(":").trim();
    if (!value) return;
    if (key === "direction") result.direction = value;
    if (key === "items") result.items = value;
    if (key === "details") result.details = value;
  });
  return result;
}

const syncHistoryColumns = [
  {
    title: "DATE",
    dataIndex: "date",
    key: "date",
    width: 160,
  },
  {
    title: "DIRECTION",
    dataIndex: "direction",
    key: "direction",
    width: 140,
    render: (dir: string) => {
      if (!dir) return null;
      const isPush = dir === "Push";
      return (
        <span
          className={`text-[13px] font-medium ${
            isPush ? "text-green-600" : "text-blue-600"
          }`}
        >
          {isPush ? "↑" : "↓"} {dir}
        </span>
      );
    },
  },
  { title: "ITEMS", dataIndex: "items", key: "items", width: 180 },
  {
    title: "STATUS",
    dataIndex: "status",
    key: "status",
    width: 120,
    render: (status: number | null) => {
      const success = status !== null && status < 400;
      return (
        <Tag
          className={`rounded-full px-3.5 py-0.5 font-semibold text-xs m-0 ${
            success
              ? "bg-green-50 text-green-600 border border-green-200"
              : "bg-red-50 text-red-600 border border-red-200"
          }`}
        >
          {success ? "Success" : "Failed"}
        </Tag>
      );
    },
  },
  { title: "DETAILS", dataIndex: "details", key: "details" },
];

interface JiraConfig {
  jiraUrl: string;
  projectKey: string;
}

interface JiraIntegrationTabProps {
  projectId: string;
}

export default function JiraIntegrationTab({
  projectId,
}: JiraIntegrationTabProps) {
  const { message, modal } = App.useApp();
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [saved, setSaved] = useState<JiraConfig>({
    jiraUrl: "",
    projectKey: "",
  });
  const [draft, setDraft] = useState<JiraConfig>(saved);
  const [syncHistory, setSyncHistory] = useState<SyncHistoryRow[]>([]);
  const [syncHistoryLoading, setSyncHistoryLoading] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setSyncHistory([]);
      return;
    }

    const cached = syncHistoryCache.get(projectId);
    const withinCooldown =
      cached && Date.now() - cached.fetchedAt < SYNC_HISTORY_COOLDOWN_MS;

    if (withinCooldown) {
      setSyncHistory(cached.rows);
      setSyncHistoryLoading(false);
      return;
    }

    let cancelled = false;
    setSyncHistoryLoading(true);
    fetchApplicationLogs({ projectId, service: "jira", limit: 100 })
      .then(({ logs }) => {
        if (cancelled) return;
        const rows = logs
          .filter((entry) => SYNC_ENDPOINT_PATTERN.test(entry.endpoint))
          .map((entry): SyncHistoryRow => {
            const { direction, items, details } = parseSyncMessage(
              entry.message,
            );
            return {
              key: entry.id,
              date: new Date(entry.loggedAt).toLocaleString(),
              direction,
              items,
              details,
              status: entry.statusCode,
            };
          });
        syncHistoryCache.set(projectId, { rows, fetchedAt: Date.now() });
        setSyncHistory(rows);
      })
      .catch((error) => {
        if (!cancelled) {
          console.error("Failed to load Jira sync history:", error);
          setSyncHistory([]);
        }
      })
      .finally(() => {
        if (!cancelled) setSyncHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setLoading(true);
    getJiraConfig(projectId)
      .then((config) => {
        if (cancelled) return;
        const next: JiraConfig = {
          jiraUrl: config.jiraUrl,
          projectKey: config.projectKey,
        };
        setSaved(next);
        setDraft(next);
        setIsConnected(config.isConnected);
      })
      .catch((error) => {
        if (!cancelled) {
          console.error("Failed to load Jira config:", error);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const startEdit = () => {
    setDraft(saved);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      const result = await saveJiraConfig(projectId, {
        jiraUrl: draft.jiraUrl,
        projectKey: draft.projectKey,
      });
      const next: JiraConfig = {
        jiraUrl: result.jiraUrl,
        projectKey: result.projectKey,
      };
      setSaved(next);
      setDraft(next);
      setIsConnected(false);
      setIsEditing(false);
      message.success("Jira configuration saved.");
    } catch (error) {
      message.error(
        error instanceof Error
          ? error.message
          : "Failed to save Jira configuration.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(saved);
    setIsEditing(false);
  };

  const handleTestConnection = async () => {
    if (!projectId) return;
    setTesting(true);
    try {
      const result = await testJiraConnection(projectId);
      setIsConnected(result.success);
      modal[result.success ? "success" : "error"]({
        title: result.success ? "Connection successful" : "Connection failed",
        content: result.message,
      });
    } catch (error) {
      setIsConnected(false);
      Modal.error({
        title: "Connection failed",
        content:
          error instanceof Error
            ? error.message
            : "Unable to test the Jira connection.",
      });
    } finally {
      setTesting(false);
    }
  };

  const statusTag = isConnected ? (
    <Tag className="rounded-full px-3.5 py-0.5 font-semibold text-xs bg-green-50 text-green-600 border border-green-200 m-0">
      Connected
    </Tag>
  ) : (
    <Tag className="rounded-full px-3.5 py-0.5 font-semibold text-xs bg-red-50 text-red-600 border border-red-200 m-0">
      Not Connected
    </Tag>
  );

  return (
    <div className="workspace__body">
      {/* ── Jira Configuration Card ── */}
      <div className="project-page__detail-card">
        {/* Header row */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <JiraDiamondIcon />
            <span className="text-sm font-semibold text-gray-900">
              Jira Configuration
            </span>
          </div>
          {statusTag}
        </div>

        {/* Fields grid */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-6">
          <div>
            <div className="text-xs text-gray-500 mb-1.5">Jira URL</div>
            <Input
              value={isEditing ? draft.jiraUrl : saved.jiraUrl}
              onChange={
                isEditing
                  ? (e) => setDraft((d) => ({ ...d, jiraUrl: e.target.value }))
                  : undefined
              }
              readOnly={!isEditing}
              placeholder="https://your-domain.atlassian.net"
              disabled={loading}
              className={`rounded-lg! text-gray-700! ${
                isEditing ? "bg-white!" : "bg-gray-50!"
              }`}
            />
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1.5">Project Key</div>
            <Input
              value={isEditing ? draft.projectKey : saved.projectKey}
              onChange={
                isEditing
                  ? (e) =>
                      setDraft((d) => ({ ...d, projectKey: e.target.value }))
                  : undefined
              }
              readOnly={!isEditing}
              placeholder="—"
              disabled={loading}
              className={`rounded-lg! text-gray-700! ${
                isEditing ? "bg-white!" : "bg-gray-50!"
              }`}
            />
          </div>
        </div>

        <p className="text-xs text-gray-500 mb-6">
          Your Jira email and API token are set in your{" "}
          <Link
            href="/profile"
            className="text-[#1f3333] font-medium underline"
          >
            Profile
          </Link>
          .
        </p>

        {/* Action buttons */}
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
                Save Config
              </Button>
            </>
          ) : (
            <>
              <Button
                icon={<EditOutlined />}
                onClick={startEdit}
                className="rounded-lg!"
                disabled={loading}
              >
                Edit Config
              </Button>
              <Button
                icon={<SyncOutlined />}
                onClick={handleTestConnection}
                loading={testing}
                disabled={loading || !saved.jiraUrl || !saved.projectKey}
                className="bg-[#1f3333]! border-[#1f3333]! text-white! rounded-lg!"
              >
                Test Connection
              </Button>
            </>
          )}
        </div>
      </div>

      {/* ── Sync History Card ── */}
      <div className="project-page__detail-card">
        <span className="project-card__heading block mb-4">Sync History</span>
        <Table
          className="project-tabs-table"
          columns={syncHistoryColumns}
          dataSource={syncHistory}
          pagination={syncHistory.length > 10 ? { pageSize: 10 } : false}
          loading={syncHistoryLoading}
          size="small"
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No sync history yet"
              />
            ),
          }}
        />
      </div>
    </div>
  );
}
