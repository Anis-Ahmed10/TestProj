"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Table, Tag, Empty } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import FlaskIcon from "@/app/(protected)/clients/project/assets/icons/FlaskIcon";
import TargetIcon from "@/app/(protected)/clients/project/assets/icons/TargetIcon";
import SearchInfoIcon from "@/app/(protected)/clients/project/assets/icons/SearchInfoIcon";
import { setProjectId as setRegressionProjectId } from "@/store/slices/regressionAnalyserSlice";
import { useAppDispatch } from "@/store/store";
import { setProjectId as setTestGenProjectId } from "@/store/slices/testGenerationSlice";
import { setProjectId as setAutomationProjectId } from "@/store/slices/automationSelectionSlice";
import { CSV_BOM, toCsv } from "@/utils/csv/csv";
import { downloadExcel } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import {
  fetchApplicationLogs,
  ApplicationLogEntry,
} from "@/services/applicationlogsservice";

interface AIToolsTabProps {
  projectId?: string;
  projectName?: string;
}
const PIPELINE_HISTORY_COOLDOWN_MS = 60_000;
const pipelineHistoryCache = new Map<
  string,
  { rows: PipelineRow[]; fetchedAt: number }
>();

const AI_TOOLS = [
  {
    key: "test-generator",
    label: "Test Case Generator",
    description:
      "Paste user stories, get structured test cases powered by Claude AI",
    iconBg: "bg-[#d4ece8]",
    icon: <FlaskIcon />,
    href: "/test-generator",
  },
  {
    key: "automation-selector",
    label: "Automation Selector",
    description: "AI recommends which test cases to automate for maximum ROI",
    iconBg: "bg-[#fef3c7]",
    icon: <TargetIcon />,
    href: "/automation-selector",
  },
  {
    key: "regression-analyser",
    label: "Regression Analyser",
    description: "Identify impacted test cases from change descriptions",
    iconBg: "bg-[#dbeafe]",
    icon: <SearchInfoIcon />,
    href: "/regression-analyser",
  },
];

const PIPELINE_SOURCES: Array<{
  service: string;
  endpoints: string[];
  label: string;
  scopedByProject: boolean;
}> = [
  {
    service: "database",
    endpoints: ["/database/save-test-cases", "/database/save-stories"],
    label: "Test Case Generator",
    scopedByProject: true,
  },
  {
    service: "automation_selection",
    endpoints: [],
    label: "Automation Selector",
    scopedByProject: true,
  },
  {
    service: "regression_analyser",
    endpoints: [],
    label: "Regression Analyser",
    scopedByProject: true,
  },
];

const PROJECT_SCOPED_SERVICES = PIPELINE_SOURCES.filter(
  (s) => s.scopedByProject,
).map((s) => s.service);
const UNSCOPED_SERVICES = PIPELINE_SOURCES.filter(
  (s) => !s.scopedByProject,
).map((s) => s.service);

function pipelineSourceFor(
  serviceName: string,
  endpoint: string,
): { label: string } | null {
  const match = PIPELINE_SOURCES.find(
    (s) =>
      s.service === serviceName &&
      (s.endpoints.length === 0 || s.endpoints.includes(endpoint)),
  );
  return match ? { label: match.label } : null;
}

function parsePipelineMessage(message: string | null): {
  input: string;
  output: string;
  version: string;
} {
  const result = { input: "—", output: "—", version: "—" };
  if (!message) return result;
  message.split("|").forEach((part) => {
    const [key, ...rest] = part.split(":");
    const value = rest.join(":").trim();
    if (!value) return;
    if (key === "input") result.input = value;
    if (key === "output") result.output = value;
    if (key === "version") result.version = value;
  });
  return result;
}

function statusTagProps(statusCode: number | null): {
  label: string;
  className: string;
} {
  if (statusCode === null) {
    return {
      label: "Unknown",
      className: "bg-gray-50 text-gray-500 border border-gray-200",
    };
  }
  if (statusCode < 400) {
    return {
      label: "Success",
      className: "bg-green-50 text-green-600 border border-green-200",
    };
  }
  return {
    label: "Failed",
    className: "bg-red-50 text-red-600 border border-red-200",
  };
}

interface PipelineRow {
  key: string;
  date: string;
  pipeline: string;
  input: string;
  output: string;
  user: string;
  status: number | null;
}

const pipelineColumns = [
  { title: "DATE", dataIndex: "date", key: "date", width: 140 },
  { title: "PIPELINE", dataIndex: "pipeline", key: "pipeline", width: 180 },
  { title: "INPUT", dataIndex: "input", key: "input", width: 160 },
  { title: "OUTPUT", dataIndex: "output", key: "output", width: 160 },
  { title: "USER", dataIndex: "user", key: "user", width: 130 },
  {
    title: "STATUS",
    dataIndex: "status",
    key: "status",
    width: 100,
    render: (status: number | null) => {
      const { label, className } = statusTagProps(status);
      return (
        <Tag
          className={`rounded-full px-2.5 py-px font-semibold text-xs ${className}`}
        >
          {label}
        </Tag>
      );
    },
  },
];

function toPipelineRow(entry: ApplicationLogEntry): PipelineRow | null {
  const source = pipelineSourceFor(entry.serviceName, entry.endpoint);
  if (!source) return null;
  const { input, output } = parsePipelineMessage(entry.message);
  return {
    key: entry.id,
    date: new Date(entry.loggedAt).toLocaleString(),
    pipeline: source.label,
    input,
    output,
    user: entry.userName ?? entry.userEmail ?? "—",
    status: entry.statusCode,
  };
}

export default function AIToolsTab({
  projectId,
  projectName,
}: AIToolsTabProps) {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRow[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setPipelineRuns([]);
      return;
    }

    const cached = pipelineHistoryCache.get(projectId);
    const withinCooldown =
      cached && Date.now() - cached.fetchedAt < PIPELINE_HISTORY_COOLDOWN_MS;

    if (withinCooldown) {
      setPipelineRuns(cached.rows);
      setLogsLoading(false);
      return;
    }

    let cancelled = false;
    setLogsLoading(true);

    Promise.all([
      PROJECT_SCOPED_SERVICES.length
        ? fetchApplicationLogs({
            projectId,
            service: PROJECT_SCOPED_SERVICES.join(","),
            limit: 100,
          })
        : Promise.resolve({ logs: [] as ApplicationLogEntry[], total: 0 }),
      UNSCOPED_SERVICES.length
        ? fetchApplicationLogs({
            service: UNSCOPED_SERVICES.join(","),
            limit: 100,
          })
        : Promise.resolve({ logs: [] as ApplicationLogEntry[], total: 0 }),
    ])
      .then(([scoped, unscoped]) => {
        if (cancelled) return;
        const rows = [...scoped.logs, ...unscoped.logs]
          .map(toPipelineRow)
          .filter((row): row is PipelineRow => row !== null)
          .sort(
            (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
          );
        pipelineHistoryCache.set(projectId, { rows, fetchedAt: Date.now() });
        setPipelineRuns(rows);
        setPipelineError(null);
      })
      .catch((error) => {
        if (!cancelled) {
          console.error("Failed to load pipeline run history:", error);
          setPipelineRuns([]);
          setPipelineError("Couldn't load pipeline history. Please retry.");
        }
      })
      .finally(() => {
        if (!cancelled) setLogsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleToolClick = (toolKey: string, href: string) => {
    if (projectId) {
      if (toolKey === "test-generator") {
        dispatch(setTestGenProjectId(projectId));
      } else if (toolKey === "automation-selector") {
        dispatch(setAutomationProjectId(projectId));
      } else if (toolKey === "regression-analyser") {
        dispatch(setRegressionProjectId(projectId));
      }
    }
    router.push(href);
  };

  return (
    <div className="workspace__body">
      {projectName && (
        <p className="text-[13px] text-gray-500 mb-3">
          Opens with <span className="font-semibold">{projectName}</span>{" "}
          pre-selected — you can pick a different project once inside.
        </p>
      )}
      <div className="grid grid-cols-3 gap-4 mb-5">
        {AI_TOOLS.map((tool) => (
          <div
            key={tool.key}
            onClick={() => handleToolClick(tool.key, tool.href)}
            className="bg-white border border-gray-200 rounded-[14px] px-5 py-7 cursor-pointer text-center transition-shadow duration-150 hover:shadow-[0_4px_16px_rgba(0,0,0,0.08)]"
          >
            <div
              className={`w-14 h-14 rounded-xl ${tool.iconBg} flex items-center justify-center mx-auto mb-4`}
            >
              {tool.icon}
            </div>
            <div className="font-bold text-sm text-gray-900 mb-2">
              {tool.label}
            </div>
            <p className="text-[13px] text-gray-500 m-0 leading-relaxed">
              {tool.description}
            </p>
          </div>
        ))}
      </div>

      <div className="project-page__detail-card">
        <div className="flex items-center justify-between mb-4">
          <span className="project-card__heading">Pipeline Run History</span>
          <Button
            icon={<DownloadOutlined />}
            className="rounded-lg text-[13px]"
            disabled={pipelineRuns.length === 0}
            onClick={() => {
              const header = [
                "Date",
                "Pipeline",
                "Input",
                "Output",
                "User",
                "Status",
              ];
              const rows = pipelineRuns.map((r) => [
                r.date,
                r.pipeline,
                r.input,
                r.output,
                r.user,
                statusTagProps(r.status).label,
              ]);
              downloadExcel(
                new Blob([CSV_BOM + toCsv([header, ...rows])], {
                  type: "text/csv;charset=utf-8;",
                }),
                "pipeline-run-history.csv",
              );
            }}
          >
            Export
          </Button>
        </div>
        <Table
          className="project-tabs-table"
          columns={pipelineColumns}
          dataSource={pipelineRuns}
          rowKey="key"
          loading={logsLoading}
          pagination={pipelineRuns.length > 10 ? { pageSize: 10 } : false}
          size="small"
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No pipeline runs yet"
              />
            ),
          }}
        />
      </div>
    </div>
  );
}
