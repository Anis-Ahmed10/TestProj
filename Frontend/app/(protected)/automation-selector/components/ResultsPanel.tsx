"use client";

import React, { useMemo, useCallback } from "react";
import {
  FireOutlined,
  SyncOutlined,
  AppstoreOutlined,
  SearchOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import AITable from "@/components/AITable";
import AutomationMix from "./AutomationMix";
import ExpandedRowDetail from "./ExpandedRowDetail";
import type {
  AutomationTestCase,
  CategoryConfig,
  AutomationMixData,
} from "@/types/automationCandidate";
import {
  filterTestCases,
  computeAutomationMix,
  getUniqueLevels,
} from "@/utils/automationSelector/automationSelectorHelpers";
import { App } from "antd";
import { downloadExcel } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";

interface ResultsPanelProps {
  category: CategoryConfig;
  selectedFilter: "all" | "automate" | "review" | "manual";
  searchQuery: string;
  levelFilter: string;
  onFilterChange: (filter: "all" | "automate" | "review" | "manual") => void;
  onSearchChange: (query: string) => void;
  onLevelFilterChange: (level: string) => void;
  onToggleTestCase: (id: string) => void;
  onToggleAll: (checked: boolean, visibleIds: string[]) => void;
}

const categoryIconMap: Record<string, React.ElementType> = {
  FireOutlined,
  SyncOutlined,
  AppstoreOutlined,
};

// Score color helper
const getScoreFillColor = (score: number) => {
  if (score > 0.65) return "var(--as-green)";
  if (score >= 0.4) return "var(--as-amber)";
  return "var(--as-gray-400)";
};

const EXPORT_COLUMNS = [
  { header: "TC ID", key: "tcKey", width: 22 },
  { header: "Test Case", key: "name", width: 52 },
  { header: "Classification", key: "classification", width: 16 },
  { header: "Level", key: "level", width: 10 },
  { header: "Score", key: "score", width: 10, numFmt: "0.00" },
  { header: "Confidence", key: "confidence", width: 12, numFmt: "0.00" },
  { header: "Reasoning", key: "reasoning", width: 80 },
];

const getConfColor = (conf: number) => {
  if (conf > 0.8) return "var(--as-green)";
  if (conf >= 0.6) return "var(--as-amber)";
  return "var(--as-red)";
};

export default function ResultsPanel({
  category,
  selectedFilter,
  searchQuery,
  levelFilter,
  onFilterChange,
  onSearchChange,
  onLevelFilterChange,
  onToggleTestCase,
  onToggleAll,
}: ResultsPanelProps) {
  const { message } = App.useApp();

  // Filtered test cases
  const filteredTCs = useMemo(
    () =>
      filterTestCases(
        category.testCases,
        selectedFilter,
        searchQuery,
        levelFilter,
      ),
    [category.testCases, selectedFilter, searchQuery, levelFilter],
  );

  // Level options
  const levelOptions = useMemo(
    () => getUniqueLevels(category.testCases),
    [category.testCases],
  );

  // Automation mix
  const mix: AutomationMixData = useMemo(
    () => computeAutomationMix(category.testCases),
    [category.testCases],
  );

  // Selection counts
  const selectedCount = useMemo(
    () => category.testCases.filter((tc) => tc.checked).length,
    [category.testCases],
  );
  const reviewPending = useMemo(
    () =>
      category.testCases.filter(
        (tc) => tc.classification === "REVIEW" && !tc.checked,
      ).length,
    [category.testCases],
  );

  // Category icon
  const CatIcon = categoryIconMap[category.icon] || AppstoreOutlined;

  // Filters
  const filterTabs: {
    key: "all" | "automate" | "review" | "manual";
    label: string;
    count: number;
    colorClass?: string;
  }[] = [
    { key: "all", label: "All", count: category.counts.all },
    {
      key: "automate",
      label: "Automate",
      count: category.counts.automate,
      colorClass: "as-ftab--automate",
    },
    {
      key: "review",
      label: "Review",
      count: category.counts.review,
      colorClass: "as-ftab--review",
    },
    {
      key: "manual",
      label: "Manual",
      count: category.counts.manual,
      colorClass: "as-ftab--manual",
    },
  ];

  // Table columns
  const columns = useMemo(
    () => [
      {
        title: "TC ID",
        dataIndex: "tcKey",
        key: "tcKey",
        width: 140,
        ellipsis: true,
        render: (val: string) => <span className="as-tc-id">{val}</span>,
      },
      {
        title: "Test Case",
        dataIndex: "name",
        key: "name",
        ellipsis: true,
      },
      {
        title: "Classification",
        dataIndex: "classification",
        key: "classification",
        width: 120,
        ellipsis: true,
        render: (val: string) => {
          const clsMap: Record<string, { css: string; label: string }> = {
            AUTOMATE: { css: "as-sp-auto", label: "Automate" },
            REVIEW: { css: "as-sp-review", label: "Review" },
            KEEP_MANUAL: { css: "as-sp-manual", label: "Keep Manual" },
          };
          const info = clsMap[val] || clsMap.KEEP_MANUAL;
          return (
            <span className={`as-score-pill ${info.css}`}>{info.label}</span>
          );
        },
      },
      {
        title: "Level",
        dataIndex: "level",
        key: "level",
        width: 110,
        ellipsis: true,
        render: (val: string | null) => {
          if (!val)
            return (
              <span style={{ color: "var(--as-gray-400)", fontSize: "10px" }}>
                —
              </span>
            );
          const badgeMap: Record<string, string> = {
            UNIT: "as-badge-unit",
            API: "as-badge-api",
            UI: "as-badge-ui",
          };
          return (
            <span
              className={`as-badge ${
                badgeMap[val.toUpperCase()] || "as-badge-api"
              }`}
            >
              {val.toUpperCase()}
            </span>
          );
        },
      },
      {
        title: "Score",
        dataIndex: "score",
        key: "score",
        width: 130,
        sorter: (a: AutomationTestCase, b: AutomationTestCase) =>
          a.score - b.score,
        render: (val: number) => {
          const fillColor = getScoreFillColor(val);
          return (
            <div className="as-score-bar">
              <div className="as-score-bar-bg">
                <div
                  className="as-score-bar-fill"
                  style={{
                    width: `${Math.round(val * 100)}%`,
                    background: fillColor,
                  }}
                />
              </div>
              <div className="as-score-bar-val" style={{ color: fillColor }}>
                {val.toFixed(2)}
              </div>
            </div>
          );
        },
      },
      {
        title: "Confidence",
        dataIndex: "confidence",
        key: "confidence",
        width: 120,
        sorter: (a: AutomationTestCase, b: AutomationTestCase) =>
          a.confidence - b.confidence,
        render: (val: number) => (
          <span className="as-conf-cell" style={{ color: getConfColor(val) }}>
            {Math.round(val * 100)}%
          </span>
        ),
      },
    ],
    [],
  );

  // Row selection
  const selectedRowKeys = useMemo(
    () => filteredTCs.filter((tc) => tc.checked).map((tc) => tc.id),
    [filteredTCs],
  );

  const rowSelection = useMemo(
    () => ({
      selectedRowKeys,
      onSelect: (record: AutomationTestCase) => {
        if (record.classification !== "KEEP_MANUAL") {
          onToggleTestCase(record.id);
        }
      },
      onSelectAll: (selected: boolean) => {
        onToggleAll(
          selected,
          filteredTCs.map((tc) => tc.id),
        );
      },
      getCheckboxProps: (record: AutomationTestCase) => ({
        disabled: record.classification === "KEEP_MANUAL",
      }),
    }),
    [selectedRowKeys, filteredTCs, onToggleTestCase, onToggleAll],
  );

  const downloadSelectedRows = useCallback(async () => {
    const selected = category.testCases.filter((tc) => tc.checked);
    if (!selected.length) return 0;

    const ExcelJS = (await import("exceljs")).default;
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet("Automation Candidates");
    worksheet.columns = EXPORT_COLUMNS.map(
      ({ header, key, width, numFmt }) => ({
        header,
        key,
        width,
        style: {
          numFmt,
          alignment: { vertical: "top" as const, wrapText: true },
        },
      }),
    );

    selected.forEach((tc) => {
      worksheet.addRow({
        tcKey: tc.tcKey,
        name: tc.name,
        classification: tc.classification,
        level: tc.level ?? "",
        score: tc.score,
        confidence: tc.confidence,
        reasoning: tc.reasoning.join("\n"),
      });
    });

    const headerRow = worksheet.getRow(1);
    headerRow.font = { bold: true };
    headerRow.alignment = { vertical: "top", wrapText: true };
    worksheet.views = [{ state: "frozen", ySplit: 1 }];

    const buffer = await workbook.xlsx.writeBuffer();
    downloadExcel(
      new Blob([buffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
      `automation_candidates_${category.key}.xlsx`,
    );
    return selected.length;
  }, [category.testCases, category.key]);

  const handleExportList = useCallback(async () => {
    try {
      const exported = await downloadSelectedRows();
      if (!exported) {
        message.warning("Select at least one test case to export.");
        return;
      }
      message.success(`Exported ${exported} TCs as Excel.`);
    } catch {
      message.error("Could not build the Excel file. Please try again.");
    }
  }, [downloadSelectedRows, message]);

  const handleApproveExport = useCallback(async () => {
    if (reviewPending > 0) {
      message.warning(
        `${reviewPending} Review TCs have not been decided yet. Please select or dismiss them before exporting.`,
      );
      return;
    }
    try {
      const exported = await downloadSelectedRows();
      if (!exported) {
        message.warning("Select at least one test case to export.");
        return;
      }
      message.success(`Exported ${exported} TCs for automation scripting.`);
    } catch {
      message.error("Could not build the Excel file. Please try again.");
    }
  }, [reviewPending, downloadSelectedRows, message]);

  return (
    <div className="as-results-panel">
      {/* Header */}
      <div className="as-results-header">
        <div className="as-results-header-left">
          <div className="as-results-title">
            <CatIcon style={{ color: category.iconColor }} />
            <span>{category.title}</span>
          </div>
          <div className="as-results-meta">{category.meta}</div>
          {category.status !== "scored" && (
            <div className="as-review-gate">
              <WarningOutlined className="as-review-gate-icon" />
              <p>
                <strong>Incomplete analysis</strong> —{" "}
                {category.failureReason ||
                  "some test cases could not be scored for this category."}
              </p>
            </div>
          )}
        </div>
        <div className="as-results-header-right">
          <div className="as-filter-tabs">
            {filterTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`as-ftab ${
                  tab.colorClass && selectedFilter !== tab.key
                    ? tab.colorClass
                    : ""
                } ${selectedFilter === tab.key ? "as-ftab--active" : ""}`}
                onClick={() => onFilterChange(tab.key)}
              >
                {tab.label} <span className="as-ftab-cnt">{tab.count}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Search Row */}
      <div className="as-search-row">
        <div className="as-search-box">
          <SearchOutlined className="as-search-box-icon" />
          <input
            type="text"
            className="as-search-input"
            placeholder="Search by TC ID or name…"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <select
          className="as-filter-select"
          value={levelFilter || "All Levels"}
          onChange={(e) => onLevelFilterChange(e.target.value)}
        >
          <option>All Levels</option>
          {levelOptions.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
      </div>

      {/* Automation Mix */}
      <AutomationMix mix={mix} />

      {/* Table */}
      {filteredTCs.length > 0 ? (
        <AITable
          columns={columns}
          datasource={filteredTCs}
          rowKey="id"
          rowSelection={rowSelection}
          pagination={{
            pageSize: 10,
            placement: ["bottomCenter"],
            showSizeChanger: false,
          }}
          rowClassName={(record: AutomationTestCase) =>
            record.classification === "KEEP_MANUAL" ? "as-row-manual" : ""
          }
          expandable={{
            expandedRowRender: (record: AutomationTestCase) => (
              <ExpandedRowDetail record={record} />
            ),
            rowExpandable: () => true,
            expandRowByClick: true,
            showExpandColumn: false,
          }}
        />
      ) : (
        <div className="as-empty-state">
          <InboxOutlined className="as-empty-icon" />
          <div className="as-empty-title">No test cases match your filters</div>
          <div className="as-empty-desc">
            Try adjusting the classification filter, search query, or
            module/level selections.
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="as-results-footer">
        <div className="as-footer-left">
          <span>
            <span className="as-sel-count">{selectedCount}</span> TCs selected
            for automation
          </span>
          {reviewPending > 0 && (
            <div className="as-review-gate">
              <WarningOutlined className="as-review-gate-icon" />
              <p>
                <strong>{reviewPending} under Review</strong> — TA must decide
                before export
              </p>
            </div>
          )}
        </div>
        <div className="as-footer-actions">
          <button
            className="as-btn as-btn-outline as-btn-sm"
            onClick={handleExportList}
            disabled={selectedCount === 0}
            type="button"
          >
            <FileTextOutlined />
            Export List
          </button>
          <button
            className="as-btn as-btn-green as-btn-sm"
            onClick={handleApproveExport}
            disabled={selectedCount === 0}
            type="button"
          >
            <CheckCircleOutlined />
            Approve &amp; Export
          </button>
        </div>
      </div>
    </div>
  );
}
