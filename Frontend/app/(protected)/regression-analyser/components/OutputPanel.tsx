"use client";

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";
import { Button, Tag, App } from "antd";
import {
  SearchOutlined,
  DownloadOutlined,
  RedoOutlined,
  SafetyCertificateOutlined,
  PieChartOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import SummaryMetrics from "./SummaryMetrics";
import ImpactTable from "./ImpactTable";
import {
  ImpactAnalysisResult,
  STRATEGIES,
  type RegressionStrategy,
  TestCaseImpactRow,
} from "@/types/impactAnalyzer";
import {
  generateRegressionAnalysisExcel,
  buildRegressionExportFilename,
} from "@/utils/regressionAnalyser/regressionAnalyserExport";
import { downloadExcel } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";

function formatTimestamp(isoString: string): string {
  return new Date(isoString).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface OutputPanelProps {
  result: ImpactAnalysisResult | null;
  isAnalyzing: boolean;
  strategy: RegressionStrategy;
  onReanalyse: () => void;
  canAnalyze: boolean;
  canRunAnalysis: boolean;
  lastUpdated: string | null;
  isCoolingDown?: boolean;
  projectName: string;
}

function OutputPanel({
  result,
  isAnalyzing,
  strategy,
  onReanalyse,
  canAnalyze,
  canRunAnalysis,
  lastUpdated,
  isCoolingDown = false,
  projectName,
}: OutputPanelProps) {
  const { message } = App.useApp();
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [filteredData, setFilteredData] = useState<TestCaseImpactRow[] | null>(
    null,
  );
  const [isExporting, setIsExporting] = useState(false);
  const isExportingRef = useRef(false);

  useEffect(() => {
    if (result) {
      setSelectedRowKeys(result.testCases.map((tc) => tc.id));
      setFilteredData(result.testCases);
    } else {
      setSelectedRowKeys([]);
      setFilteredData(null);
    }
  }, [result]);

  const activeTestCases = filteredData ?? result?.testCases ?? [];

  const selectedTestCases = useMemo(() => {
    const selectedSet = new Set(selectedRowKeys);
    return activeTestCases.filter((tc) => selectedSet.has(tc.id));
  }, [activeTestCases, selectedRowKeys]);

  const handleExport = useCallback(async () => {
    if (!result || selectedTestCases.length === 0 || isExportingRef.current)
      return;
    isExportingRef.current = true;
    setIsExporting(true);

    try {
      const blob = await generateRegressionAnalysisExcel(selectedTestCases);

      const fileName = buildRegressionExportFilename(projectName);
      downloadExcel(blob, fileName);

      message.success(
        `Regression analysis exported successfully (${
          selectedTestCases.length
        } test case${selectedTestCases.length === 1 ? "" : "s"}).`,
      );
    } catch (error) {
      console.error("Regression analysis export failed:", error);
      message.error("Failed to export regression analysis. Please try again.");
    } finally {
      isExportingRef.current = false;
      setIsExporting(false);
    }
  }, [result, selectedTestCases, projectName, message]);

  return (
    <div className="ra-card ra-results-panel">
      <div className="ra-card-header ra-output-panel-header">
        <div className="ra-results-header">
          <h2 className="ra-card-title">Output — LLM Results → Export</h2>
          <Tag color="green" className="ra-side-tag">
            OUTPUT SIDE
          </Tag>
        </div>

        {/* Session tab bar */}
        <div className="ra-session-tabs">
          <div className="ra-session-tab ra-session-tab--active">
            Session 1 | {STRATEGIES[strategy].label}
            {lastUpdated ? ` · ${formatTimestamp(lastUpdated)}` : ""}
          </div>
        </div>
      </div>

      <div className="ra-card-body">
        {!result && !isAnalyzing ? (
          <div className="ra-empty-state">
            <SearchOutlined className="ra-empty-icon" />
            <p className="ra-empty-title">No analysis yet</p>
            <p className="ra-empty-subtitle">
              Enter a change description, confirm the project selected at the
              top of the page, and click &ldquo;Analyse Regression&rdquo; to see
              results.
            </p>
          </div>
        ) : isAnalyzing && !result ? (
          <div className="ra-empty-state">
            <p className="ra-empty-title ra-analyzing-title">
              Analysing impact…
            </p>
            <p className="ra-empty-subtitle">
              The AI is evaluating which test cases are affected by your change.
            </p>
          </div>
        ) : (
          result && (
            <div className="ra-fade-in ra-results-body">
              {/* Analysis Summary card */}
              <div className="ra-summary-card">
                <h4 className="ra-summary-card-title">
                  <PieChartOutlined className="ra-summary-icon" /> Analysis
                  Summary
                </h4>
                <div className="ra-summary-strategy-line">
                  Strategy applied:{" "}
                  <strong>{STRATEGIES[strategy].label}</strong>
                </div>
                <div className="ra-strategy-note">
                  <InfoCircleOutlined />
                  <span>
                    {/* MOCK: the mock analysis service doesn't yet filter results by strategy*/}
                    {STRATEGIES[strategy].note}{" "}
                    <em className="ra-strategy-note-illustrative">
                      (illustrative — not yet applied to the results below)
                    </em>
                  </span>
                </div>

                {/* Reuses the existing SummaryMetrics component */}
                <SummaryMetrics summary={result.summary} />

                {result.analysisIssues.length > 0 && (
                  <div className="ra-strategy-note ra-analysis-issues-note">
                    <InfoCircleOutlined />
                    <span>
                      {result.analysisIssues.length} issue
                      {result.analysisIssues.length === 1 ? "" : "s"} occurred
                      during analysis — some test cases may be missing from the
                      results below.
                    </span>
                  </div>
                )}

                <div className="ra-summary-meta">
                  <span className="ra-summary-meta-item">
                    <SafetyCertificateOutlined /> Coverage confidence:{" "}
                    <strong>{result.summary.confidence}%</strong>
                  </span>
                </div>
              </div>

              {/* Detailed table*/}
              <div className="ra-results-table-heading">
                <span>
                  {selectedTestCases.length} of {activeTestCases.length}{" "}
                  selected
                  {result && activeTestCases.length !== result.testCases.length
                    ? ` (filtered from ${result.testCases.length})`
                    : ""}
                </span>
              </div>
              <ImpactTable
                key={lastUpdated ?? "initial"}
                data={result.testCases}
                selectedRowKeys={selectedRowKeys}
                onSelectionChange={setSelectedRowKeys}
                onFilteredDataChange={setFilteredData}
              />
            </div>
          )
        )}
      </div>

      {/* Footer — Export / Re-analyse */}
      <div className="ra-output-panel-footer">
        <div className="ra-status-bar">
          <span className="ra-status-item">
            <span
              className={`ra-status-dot ${
                selectedTestCases.length > 0
                  ? "ra-status-dot--green"
                  : "ra-status-dot--grey"
              }`}
            />
            {selectedTestCases.length} selected
          </span>
        </div>
        <div className="ra-output-footer-actions">
          <Button
            size="small"
            icon={<DownloadOutlined />}
            disabled={!result || selectedTestCases.length === 0 || isExporting}
            loading={isExporting}
            onClick={handleExport}
          >
            {isExporting ? "Exporting…" : "Export .xlsx"}
          </Button>
          <Button
            size="small"
            icon={<RedoOutlined />}
            className="ra-reanalyse-btn"
            disabled={
              isAnalyzing || !canAnalyze || !canRunAnalysis || isCoolingDown
            }
            onClick={onReanalyse}
          >
            Re-analyse
          </Button>
        </div>
      </div>
    </div>
  );
}
export default React.memo(OutputPanel);
