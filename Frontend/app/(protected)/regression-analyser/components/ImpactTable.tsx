"use client";

import { Progress, Tag } from "antd";
import type { TableProps } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  TestCaseImpactRow,
  RecommendedAction,
  TestType,
} from "@/types/impactAnalyzer";
import AITable from "@/components/AITable";

const ACTION_TAG_MAP: Record<
  RecommendedAction,
  { color: string; label: string }
> = {
  "Must Run": { color: "error", label: "MUST RUN" },
  "Should Run": { color: "warning", label: "SHOULD RUN" },
  "Can Skip": { color: "success", label: "CAN SKIP" },
};

const ACTION_COLOR: Record<RecommendedAction, string> = {
  "Must Run": "#ef4444",
  "Should Run": "#f59e0b",
  "Can Skip": "#22c55e",
};

const columns: ColumnsType<TestCaseImpactRow> = [
  {
    title: "Test Case",
    dataIndex: "testCaseKey",
    key: "testCaseKey",
    width: 140,
    render: (value: string) => (
      <span style={{ fontFamily: "monospace", fontSize: 12, color: "#4b5563" }}>
        {value}
      </span>
    ),
  },
  {
    title: "Test Case Name",
    dataIndex: "testCaseName",
    key: "testCaseName",
    ellipsis: true,
    render: (value: string) => (
      <span style={{ fontWeight: 500, color: "#111827" }}>{value}</span>
    ),
  },
  {
    title: "Tier",
    dataIndex: "tier",
    key: "tier",
    width: 100,
    align: "center",
    filters: [
      { text: "Smoke", value: "Smoke" },
      { text: "Sanity", value: "Sanity" },
      { text: "Full", value: "Full" },
    ],
    onFilter: (value, record) => record.tier === value,
    render: (tier: string) => (
      <Tag
        style={{
          fontWeight: 500,
          fontSize: 10,
          letterSpacing: "0.04em",
          borderRadius: 4,
        }}
      >
        {tier.toUpperCase()}
      </Tag>
    ),
  },
  {
    title: "Confidence",
    dataIndex: "confidence",
    key: "confidence",
    width: 180,
    sorter: (a, b) => a.confidence - b.confidence,
    defaultSortOrder: "descend",
    render: (confidence: number, record: TestCaseImpactRow) => (
      <div className="ra-progress-cell">
        <Progress
          className="ra-progress-bar"
          percent={confidence}
          showInfo={false}
          strokeColor={ACTION_COLOR[record.recommendedAction]}
          railColor="#f3f4f6"
          size="small"
          style={{ flex: 1, marginBottom: 0 }}
        />
        <span className="ra-progress-value">{confidence}%</span>
      </div>
    ),
  },
  {
    title: "Test Type",
    dataIndex: "testType",
    key: "testType",
    width: 120,
    align: "center",
    filters: [
      { text: "Automated", value: "Automated" },
      { text: "Manual", value: "Manual" },
    ],
    onFilter: (value, record) => record.testType === value,
    render: (testType: TestType | undefined) => {
      const safeTestType: TestType = testType ?? "Manual";
      return (
        <Tag
          color={safeTestType === "Automated" ? "processing" : "default"}
          style={{
            fontWeight: 500,
            fontSize: 10,
            letterSpacing: "0.04em",
            borderRadius: 4,
          }}
        >
          {safeTestType.toUpperCase()}
        </Tag>
      );
    },
  },
  {
    title: "Action",
    dataIndex: "recommendedAction",
    key: "recommendedAction",
    width: 130,
    align: "center",
    filters: [
      { text: "Must Run", value: "Must Run" },
      { text: "Should Run", value: "Should Run" },
      { text: "Can Skip", value: "Can Skip" },
    ],
    onFilter: (value, record) => record.recommendedAction === value,
    render: (action: RecommendedAction) => {
      const { color, label } = ACTION_TAG_MAP[action];
      return (
        <Tag
          color={color}
          style={{
            fontWeight: 500,
            fontSize: 10,
            letterSpacing: "0.06em",
            borderRadius: 4,
          }}
        >
          {label}
        </Tag>
      );
    },
  },
];

interface ImpactTableProps {
  data: TestCaseImpactRow[];
  selectedRowKeys?: string[];
  onSelectionChange?: (keys: string[]) => void;
  onFilteredDataChange?: (filteredData: TestCaseImpactRow[]) => void;
}
const DEFAULT_PAGE_SIZE = 10;

export default function ImpactTable({
  data,
  selectedRowKeys,
  onSelectionChange,
  onFilteredDataChange,
}: ImpactTableProps) {
  const handleTableChange: TableProps<TestCaseImpactRow>["onChange"] = (
    _pagination,
    _filters,
    _sorter,
    extra,
  ) => {
    if (extra?.currentDataSource && onFilteredDataChange) {
      onFilteredDataChange(extra.currentDataSource);
    }
  };

  return (
    <div className="ra-table-wrapper ra-table">
      <AITable<TestCaseImpactRow>
        rowKey="id"
        columns={columns}
        datasource={data}
        pageSize={DEFAULT_PAGE_SIZE}
        onChange={handleTableChange}
        expandable={{
          expandedRowRender: (record) => (
            <div className="ra-reason-cell">
              <strong>AI Reasoning:</strong> {record.reason}
            </div>
          ),
          rowExpandable: (record) => Boolean(record.reason),
        }}
        rowSelection={
          onSelectionChange
            ? {
                type: "checkbox",
                selectedRowKeys: selectedRowKeys ?? [],
                onChange: (keys) => onSelectionChange(keys as string[]),
              }
            : undefined
        }
      />
    </div>
  );
}
