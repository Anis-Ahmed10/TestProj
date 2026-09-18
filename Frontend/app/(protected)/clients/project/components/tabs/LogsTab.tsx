"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Tag, Input, Select, DatePicker, Button, Tooltip, App } from "antd";
import { SearchOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs, { Dayjs } from "dayjs";
import {
  fetchApplicationLogs,
  ApplicationLogEntry,
} from "@/services/applicationlogsservice";
import AITable from "@/components/AITable";

const { RangePicker } = DatePicker;

interface LogsTabProps {
  projectId: string;
}

const AI_SERVICE_OPTIONS = [
  { label: "All Services", value: "all" },
  { label: "Test Generator", value: "test_generator" },
  { label: "Automation Selector", value: "automation_selection" },
  { label: "Regression Analyzer", value: "regression_analyser" },
  { label: "Database", value: "database" },
  { label: "Jira", value: "jira" },
  { label: "Teams", value: "teams" },
  { label: "File Upload", value: "file_upload" },
  { label: "Projects", value: "projects" },
];

const STATUS_OPTIONS = [
  { label: "All Statuses", value: "all" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
];

function statusTag(statusCode: number | null) {
  if (statusCode === null || statusCode === undefined) {
    return (
      <Tag className="rounded-full px-2.5 py-0.5 text-xs bg-gray-50 text-gray-500 border border-gray-200">
        Unknown
      </Tag>
    );
  }
  const isSuccess = statusCode < 400;
  return (
    <Tag
      color={isSuccess ? "green" : "red"}
      className="rounded-full px-2.5 py-0.5 text-xs font-medium"
    >
      {isSuccess ? "Success" : "Failed"} ({statusCode})
    </Tag>
  );
}

function formatServiceName(service: string | null | undefined): string {
  if (!service) return "—";
  const map: Record<string, string> = {
    test_generator: "Test Generator",
    automation_selection: "Automation Selector",
    regression_analyser: "Regression Analyzer",
    database: "Database",
    jira: "Jira",
    teams: "Teams",
    file_upload: "File Upload",
    projects: "Projects",
  };
  return map[service.toLowerCase()] || service;
}

export default function LogsTab({ projectId }: LogsTabProps) {
  const { message } = App.useApp();
  const [logs, setLogs] = useState<ApplicationLogEntry[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshIndex, setRefreshIndex] = useState<number>(0);

  // Filter States
  const [selectedService, setSelectedService] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [userQuery, setUserQuery] = useState<string>("");
  const [dateRange, setDateRange] = useState<
    [Dayjs | null, Dayjs | null] | null
  >(null);

  // Fetch application logs
  useEffect(() => {
    if (!projectId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetchApplicationLogs({
      projectId,
      service: selectedService === "all" ? undefined : selectedService,
      limit: 200,
      offset: 0,
    })
      .then((res) => {
        if (!cancelled) {
          setLogs(res.logs);
          setTotal(res.total);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load project logs:", err);
          message.error("Failed to load project logs");
          setLogs([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, selectedService, refreshIndex, message]);

  // Client-side filtering across User, Status, and Date Range
  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      // User query filter (matching "System" fallback correctly)
      if (userQuery.trim()) {
        const query = userQuery.toLowerCase().trim();
        const effectiveUserName = (log.userName || "System").toLowerCase();
        const effectiveUserEmail = (log.userEmail || "").toLowerCase();

        const userNameMatch = effectiveUserName.includes(query);
        const userEmailMatch = effectiveUserEmail.includes(query);

        if (!userNameMatch && !userEmailMatch) return false;
      }

      // Status filter
      if (
        selectedStatus === "success" &&
        (log.statusCode === null || log.statusCode >= 400)
      ) {
        return false;
      }
      if (
        selectedStatus === "failed" &&
        (log.statusCode === null || log.statusCode < 400)
      ) {
        return false;
      }

      // Date range filter
      if (dateRange && dateRange[0] && dateRange[1]) {
        const logTime = new Date(log.loggedAt).getTime();
        const startTime = dateRange[0].startOf("day").valueOf();
        const endTime = dateRange[1].endOf("day").valueOf();
        if (isNaN(logTime) || logTime < startTime || logTime > endTime) {
          return false;
        }
      }

      return true;
    });
  }, [logs, userQuery, selectedStatus, dateRange]);

  const logColumns = useMemo(
    () => [
      {
        title: "Timestamp",
        dataIndex: "loggedAt",
        key: "loggedAt",
        width: 170,
        render: (val: string) => {
          const d = dayjs(val);
          return (
            <span className="text-gray-700 text-xs font-medium whitespace-nowrap">
              {d.isValid() ? d.format("YYYY-MM-DD HH:mm:ss") : val || "—"}
            </span>
          );
        },
      },
      {
        title: "User",
        key: "user",
        width: 180,
        render: (_: unknown, record: ApplicationLogEntry) => (
          <div>
            <div className="font-semibold text-gray-900 text-xs truncate max-w-[160px]">
              {record.userName || "System"}
            </div>
            {record.userEmail && (
              <div className="text-[11px] text-gray-400 truncate max-w-[160px]">
                {record.userEmail}
              </div>
            )}
          </div>
        ),
      },
      {
        title: "Service",
        dataIndex: "serviceName",
        key: "serviceName",
        width: 150,
        render: (val: string) => (
          <span className="font-medium text-gray-800 text-xs whitespace-nowrap">
            {formatServiceName(val)}
          </span>
        ),
      },
      {
        title: "Action / Endpoint",
        key: "endpoint",
        width: 200,
        render: (_: unknown, record: ApplicationLogEntry) => (
          <div className="text-left pr-4">
            <div className="font-mono text-xs text-gray-800">
              {record.endpoint || "—"}
            </div>
            {record.message && (
              <Tooltip title={record.message}>
                <div className="text-[11px] text-gray-500 truncate max-w-xl mt-0.5">
                  {record.message}
                </div>
              </Tooltip>
            )}
          </div>
        ),
      },
      {
        title: "Status",
        dataIndex: "statusCode",
        key: "statusCode",
        width: 140,
        align: "center" as const,
        render: (statusCode: number | null) => statusTag(statusCode),
      },
    ],
    [],
  );

  return (
    <div className="workspace__body">
      <div className="project-page__detail-card">
        {/* Header */}
        <div className="team-header mb-4 flex items-center justify-between">
          <span className="project-card__heading">Project Logs</span>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => setRefreshIndex((prev) => prev + 1)}
            loading={loading}
          >
            Refresh
          </Button>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5 mb-4">
          <Select
            value={selectedService}
            onChange={(val) => setSelectedService(val)}
            style={{ width: 180 }}
            options={AI_SERVICE_OPTIONS}
            className="text-xs"
          />

          <Select
            value={selectedStatus}
            onChange={(val) => setSelectedStatus(val)}
            style={{ width: 130 }}
            options={STATUS_OPTIONS}
            className="text-xs"
          />

          <RangePicker
            value={dateRange}
            onChange={(dates) =>
              setDateRange(dates as [Dayjs | null, Dayjs | null])
            }
            className="text-xs"
          />

          <Input
            placeholder="Filter by user…"
            prefix={<SearchOutlined className="text-gray-400" />}
            value={userQuery}
            onChange={(e) => setUserQuery(e.target.value)}
            allowClear
            style={{ width: 180 }}
          />
        </div>

        {/* Truncation notice indicator */}
        {total > logs.length && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1.5 mb-3">
            Showing the {logs.length} most recent of {total} entries — narrow
            the service filter to see older logs.
          </div>
        )}

        {/* Table */}
        <AITable
          columns={logColumns}
          datasource={filteredLogs}
          rowKey="id"
          loading={loading}
          pageSize={6}
        />
      </div>
    </div>
  );
}
