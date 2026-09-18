"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckOutlined, SearchOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  App,
  ConfigProvider,
  Pagination,
  Select,
  Spin,
  Tag,
  Tooltip,
} from "antd";
import { BackendProject } from "@/types/project";
import {
  TestCaseLibraryRow as TestCase,
  TestCaseFormatType,
  TCL_SELECT_THEME,
  DetailTab,
  FilterValue,
  FilterState,
  ApprovalStatusFilter,
  TEST_CASE_STATUS,
} from "@/types/testCaseLibrary";

import { CustomTestCaseTab } from "./CustomTestCaseTab";
import { StandardTestCaseTab } from "./StandardTestCaseTab";
import { BddTestCaseTab } from "./BddTestCaseTab";
import { UserStoryTab } from "./UserStoryTab";
import {
  fetchTestCasesLibrary,
  updateTestCaseStatus,
} from "@/services/testCaseService";
import { fetchProjects } from "@/services/projectService";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import AITable from "@/components/AITable";
import "../assets/css/testCasesLibrary.css";

function capitalizeWords(value: string) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatFormatLabel(fmt: TestCaseFormatType) {
  if (fmt === "bdd") return "BDD";
  if (fmt === "standard") return "Standard";
  return "Custom";
}

function formatProjectLabel(project: BackendProject) {
  return `${project.client_name} - ${project.programme_name} - ${project.name}`;
}

function formatRelativeTime(isoDate: string) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "Unknown";
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.round(diffMs / (60 * 1000));
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  const diffWeeks = Math.round(diffDays / 7);
  if (diffWeeks < 5) return `${diffWeeks}w ago`;
  const diffMonths = Math.round(diffDays / 30);
  if (diffMonths < 12) return `${diffMonths}mo ago`;
  return `${Math.round(diffDays / 365)}y ago`;
}

function toSelectOptions(
  allLabel: string,
  options: { label: string; value: string }[],
) {
  return [{ label: allLabel, value: "all" }, ...options];
}

function getUniqueLabeledOptions(
  items: TestCase[],
  key: keyof TestCase,
  formatLabel: (value: string) => string = (v) => v,
) {
  return Array.from(
    new Set(items.map((item) => String(item[key] ?? "")).filter(Boolean)),
  )
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({ label: formatLabel(value), value }));
}

function getPercentage(count: number, total: number) {
  if (total === 0) return "0% of results";
  return `${Math.round((count / total) * 100)}% of results`;
}

function getSummaryItems(items: TestCase[]) {
  const total = items.length;
  const bddCount = items.filter((i) => i.test_format_type === "bdd").length;
  const standardCount = items.filter(
    (i) => i.test_format_type === "standard",
  ).length;
  const customCount = items.filter(
    (i) => i.test_format_type === "custom",
  ).length;
  const highPriorityCount = items.filter(
    (i) => (i.priority ?? "").toLowerCase() === "high",
  ).length;
  const projectCount = new Set(items.map((i) => i.projectId).filter(Boolean))
    .size;
  const epicCount = new Set(items.map((i) => i.epicKey).filter(Boolean)).size;

  return [
    {
      label: "Total Test Cases",
      value: String(total),
      helper: `${projectCount} projects · ${epicCount} epics`,
    },
    {
      label: "BDD Format",
      value: String(bddCount),
      helper: getPercentage(bddCount, total),
    },
    {
      label: "Standard Format",
      value: String(standardCount),
      helper: getPercentage(standardCount, total),
    },
    {
      label: "Custom Format",
      value: String(customCount),
      helper: getPercentage(customCount, total),
    },
    {
      label: "High Priority",
      value: String(highPriorityCount),
      helper: getPercentage(highPriorityCount, total),
    },
  ];
}

function getTypeTagColor(type?: string): string {
  const t = (type ?? "").toLowerCase();
  if (t === "positive") return "success";
  if (t === "negative") return "error";
  if (t.includes("edge")) return "warning";
  if (t === "functional") return "blue";
  if (t === "regression") return "purple";
  if (t === "security") return "red";
  return "default";
}

function getPriorityTagColor(priority?: string): string {
  const p = (priority ?? "").toLowerCase();
  if (p === "high") return "error";
  if (p === "medium") return "warning";
  if (p === "low") return "success";
  if (p === "critical") return "magenta";
  return "default";
}

function getFormatTagColor(fmt: TestCaseFormatType): string {
  if (fmt === "bdd") return "purple";
  if (fmt === "standard") return "blue";
  return "magenta";
}

const APPROVAL_STATUS_OPTIONS = [
  { label: "Approved", value: "approved" as ApprovalStatusFilter },
  { label: "Unapproved", value: "unapproved" as ApprovalStatusFilter },
  { label: "All Statuses", value: "all" as ApprovalStatusFilter },
];

function TestCaseDetails({ testCase }: { testCase: TestCase }) {
  const [activeTab, setActiveTab] = useState<DetailTab>("test-case");

  return (
    <div className="tcl-detail">
      <div className="tcl-tabs-header">
        <div className="tcl-tabs" aria-label="Test case detail sections">
          <button
            className={`tcl-tab${
              activeTab === "test-case" ? " tcl-tab--active" : ""
            }`}
            type="button"
            onClick={() => setActiveTab("test-case")}
          >
            Test Case
          </button>
          <button
            className={`tcl-tab${
              activeTab === "user-story" ? " tcl-tab--active" : ""
            }`}
            type="button"
            onClick={() => setActiveTab("user-story")}
          >
            User Story
          </button>
          <button
            className={`tcl-tab${
              activeTab === "metadata" ? " tcl-tab--active" : ""
            }`}
            type="button"
            onClick={() => setActiveTab("metadata")}
          >
            Metadata
          </button>
        </div>
      </div>

      {activeTab === "test-case" && (
        <>
          {testCase.test_format_type === "bdd" && (
            <BddTestCaseTab testCase={testCase} />
          )}
          {testCase.test_format_type === "standard" && (
            <StandardTestCaseTab testCase={testCase} />
          )}
          {testCase.test_format_type === "custom" && (
            <CustomTestCaseTab testCase={testCase} />
          )}
        </>
      )}

      {activeTab === "user-story" && <UserStoryTab testCase={testCase} />}

      {activeTab === "metadata" && (
        <section className="tcl-detail-section">
          <p className="tcl-muted" style={{ fontSize: 13, marginTop: 14 }}>
            Metadata details coming soon.
          </p>
        </section>
      )}
    </div>
  );
}

export default function TestCasesLibraryPage() {
  const requestIdRef = useRef(0);
  const pageSize = 20;
  const { hasPermission } = usePermissions();
  const canApprove = hasPermission(PERMISSIONS.TESTCASE_UPDATE);
  const { message, modal } = App.useApp();

  const [projects, setProjects] = useState<BackendProject[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [testCasesLoading, setTestCasesLoading] = useState(false);
  const [testCasesError, setTestCasesError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [approvalStatus, setApprovalStatus] =
    useState<ApprovalStatusFilter>("approved");
  const [filters, setFilters] = useState<FilterState>({
    priority: "all",
    format: "all",
    type: "all",
  });
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [approving, setApproving] = useState(false);
  const approvingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    setProjectsLoading(true);
    setProjectsError(null);

    void fetchProjects()
      .then((data) => {
        if (cancelled) return;

        setProjects(data);
        setSelectedProjectId((current) => {
          const currentId = current ? String(current) : null;
          if (
            currentId &&
            data.some((project) => String(project.id) === currentId)
          ) {
            return currentId;
          }

          return data[0] ? String(data[0].id) : null;
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects.",
        );
      })
      .finally(() => {
        if (!cancelled) setProjectsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const loadTestCases = useCallback(() => {
    if (!selectedProjectId) {
      setTestCases([]);
      setTestCasesError(null);
      setTestCasesLoading(false);
      return;
    }

    const currentRequestId = ++requestIdRef.current;
    setExpandedId("");
    setSelectedRowKeys([]);
    setTestCases([]);
    setTestCasesError(null);
    setTestCasesLoading(true);

    void fetchTestCasesLibrary(selectedProjectId, "all")
      .then((data) => {
        if (requestIdRef.current !== currentRequestId) return;
        setTestCases(data);
      })
      .catch((err) => {
        if (requestIdRef.current !== currentRequestId) return;
        setTestCasesError(
          err instanceof Error ? err.message : "Failed to load test cases.",
        );
      })
      .finally(() => {
        if (requestIdRef.current !== currentRequestId) return;
        setTestCasesLoading(false);
      });
  }, [selectedProjectId]);

  useEffect(() => {
    setSearchQuery("");
    setCurrentPage(1);
    setFilters({ priority: "all", format: "all", type: "all" });
  }, [selectedProjectId]);

  useEffect(() => {
    loadTestCases();
  }, [loadTestCases]);

  const selectedProject = useMemo(() => {
    if (!selectedProjectId) return null;
    return (
      projects.find((project) => String(project.id) === selectedProjectId) ??
      null
    );
  }, [projects, selectedProjectId]);

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: String(project.id),
        label: formatProjectLabel(project),
      })),
    [projects],
  );

  const statusFilteredTestCases = useMemo(() => {
    if (approvalStatus === "approved") {
      return testCases.filter(
        (tc) => (tc.status ?? "").toLowerCase() === TEST_CASE_STATUS.APPROVED,
      );
    }
    if (approvalStatus === "unapproved") {
      return testCases.filter(
        (tc) => (tc.status ?? "").toLowerCase() === TEST_CASE_STATUS.PENDING,
      );
    }
    return testCases;
  }, [approvalStatus, testCases]);

  const filterOptions = useMemo(
    () => ({
      priorities: toSelectOptions(
        "All Priorities",
        getUniqueLabeledOptions(statusFilteredTestCases, "priority"),
      ),
      formats: toSelectOptions(
        "All Formats",
        getUniqueLabeledOptions(
          statusFilteredTestCases,
          "test_format_type",
          (value) => formatFormatLabel(value as TestCaseFormatType),
        ),
      ),
      types: toSelectOptions(
        "All Types",
        getUniqueLabeledOptions(
          statusFilteredTestCases,
          "type",
          capitalizeWords,
        ),
      ),
    }),
    [statusFilteredTestCases],
  );

  const visibleTestCases = useMemo(() => {
    const normalizedSearch = searchQuery.trim().toLowerCase();

    return statusFilteredTestCases.filter((tc) => {
      const matchesSearch =
        normalizedSearch.length === 0 ||
        [
          tc.tcId,
          tc.title,
          tc.storyKey,
          tc.storyTitle,
          tc.epicTitle,
          tc.projectName,
          ...(tc.tags ?? []),
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedSearch);

      return (
        matchesSearch &&
        (filters.priority === "all" ||
          (tc.priority ?? "").toLowerCase() ===
            filters.priority.toLowerCase()) &&
        (filters.format === "all" || tc.test_format_type === filters.format) &&
        (filters.type === "all" || tc.type === filters.type)
      );
    });
  }, [filters, searchQuery, statusFilteredTestCases]);

  const summaryItems = useMemo(
    () => getSummaryItems(visibleTestCases),
    [visibleTestCases],
  );

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(visibleTestCases.length / pageSize));
    if (currentPage > maxPage) {
      setCurrentPage(maxPage);
    }
  }, [currentPage, pageSize, visibleTestCases.length]);

  const paginatedTestCases = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return visibleTestCases.slice(startIndex, startIndex + pageSize);
  }, [currentPage, pageSize, visibleTestCases]);

  const paginationStart =
    visibleTestCases.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const paginationEnd = Math.min(
    currentPage * pageSize,
    visibleTestCases.length,
  );

  function updateFilter(
    key: keyof Omit<FilterState, "project">,
    value: FilterValue,
  ) {
    setCurrentPage(1);
    setExpandedId("");
    setSelectedRowKeys([]);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function handleSearchChange(value: string) {
    setCurrentPage(1);
    setExpandedId("");
    setSelectedRowKeys([]);
    setSearchQuery(value);
  }

  // --- Approval helpers ---

  const handleApprove = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0 || approvingRef.current) return;
      approvingRef.current = true;
      setApproving(true);
      try {
        const result = await updateTestCaseStatus(
          ids,
          TEST_CASE_STATUS.APPROVED,
          selectedProjectId || undefined,
        );

        // Determine which IDs actually succeeded based strictly on backend results
        const successfulIds = new Set(
          Array.isArray(result?.results)
            ? result.results.filter((r) => r.success).map((r) => r.id)
            : [],
        );
        const updatedCount = result?.updated_count ?? successfulIds.size;

        if (successfulIds.size === 0) {
          message.error("Unable to approve test case(s). Please try again.");
          return;
        }

        if (successfulIds.size < ids.length) {
          const notFoundCount =
            typeof result?.found_count === "number" &&
            result.found_count < ids.length
              ? ids.length - result.found_count
              : 0;

          if (notFoundCount > 0) {
            message.warning(
              `${successfulIds.size} of ${
                ids.length
              } test cases approved. ${notFoundCount} test case${
                notFoundCount === 1 ? "" : "s"
              } were not found in the database.`,
            );
          } else {
            message.warning(
              `${successfulIds.size} of ${ids.length} test cases approved. Some could not be updated.`,
            );
          }
        } else {
          message.success(
            updatedCount === 1
              ? "Test case approved successfully."
              : `${updatedCount} test cases approved successfully.`,
          );
        }

        // Only remove successfully approved IDs from selectedRowKeys (preserves other checked boxes)
        setSelectedRowKeys((prev) => prev.filter((k) => !successfulIds.has(k)));

        // Clear expandedId if it was one of the approved test cases
        setExpandedId((prev) => (prev && successfulIds.has(prev) ? "" : prev));

        // Update in-place to give instant zero-flicker feedback
        setTestCases((prev) =>
          prev.map((tc) =>
            successfulIds.has(tc.id)
              ? { ...tc, status: TEST_CASE_STATUS.APPROVED }
              : tc,
          ),
        );

        // Reconcile with the backend if there was any partial failure or missing ID
        if (successfulIds.size < ids.length) {
          void loadTestCases();
        }
      } catch {
        message.error("Unable to approve test case(s). Please try again.");
        void loadTestCases();
      } finally {
        approvingRef.current = false;
        setApproving(false);
      }
    },
    [loadTestCases, message, selectedProjectId],
  );

  const confirmApprove = useCallback(
    (ids: string[]) => {
      modal.confirm({
        title:
          ids.length === 1
            ? "Approve Test Case"
            : `Approve ${ids.length} Test Cases`,
        content:
          ids.length === 1
            ? "Are you sure you want to approve this test case? Once approved, it will be available across all workflows."
            : `Are you sure you want to approve ${ids.length} test cases? Once approved, they will be available across all workflows.`,
        okText: "Approve",
        cancelText: "Cancel",
        okButtonProps: {
          style: { backgroundColor: "#15803d", borderColor: "#15803d" },
        },
        onOk: () => handleApprove(ids),
      });
    },
    [modal, handleApprove],
  );

  // Eligible rows for selection: pending test cases across all matching pages
  const selectableRowKeys = useMemo(
    () =>
      new Set(
        visibleTestCases
          .filter((tc) => tc.status === TEST_CASE_STATUS.PENDING)
          .map((tc) => tc.id),
      ),
    [visibleTestCases],
  );

  // Pending test cases only on the active page
  const selectableOnCurrentPage = useMemo(
    () =>
      new Set(
        paginatedTestCases
          .filter((tc) => tc.status === TEST_CASE_STATUS.PENDING)
          .map((tc) => tc.id),
      ),
    [paginatedTestCases],
  );

  const showRowSelection = canApprove && approvalStatus !== "approved";

  const rowSelection = showRowSelection
    ? {
        selectedRowKeys,
        onChange: (keys: React.Key[]) => setSelectedRowKeys(keys as string[]),
        preserveSelectedRowKeys: true,
        getCheckboxProps: (record: TestCase) => ({
          disabled: record.status !== TEST_CASE_STATUS.PENDING,
        }),
      }
    : undefined;

  // --- Columns ---

  const testCaseColumns: ColumnsType<TestCase> = useMemo(() => {
    const cols: ColumnsType<TestCase> = [
      {
        title: "ID",
        dataIndex: "tcId",
        key: "tcId",
        width: 125,
        render: (value: string) => (
          <Tooltip title={value}>
            <span className="tcl-id-code">{value}</span>
          </Tooltip>
        ),
      },
      {
        title: "Title",
        dataIndex: "title",
        key: "title",
        width: 200,
        ellipsis: true,
        render: (value: string) => (
          <Tooltip title={value}>
            <span className="tcl-title-cell">{value}</span>
          </Tooltip>
        ),
      },
      {
        title: "Status",
        dataIndex: "status",
        key: "status",
        width: 85,
        render: (value: string) => {
          const isApproved = value === TEST_CASE_STATUS.APPROVED;
          return (
            <span
              className={`tcl-status-badge ${
                isApproved
                  ? "tcl-status-badge--approved"
                  : "tcl-status-badge--unapproved"
              }`}
            >
              {isApproved ? "Approved" : "Unapproved"}
            </span>
          );
        },
      },
      {
        title: "Type",
        dataIndex: "type",
        key: "type",
        width: 70,
        render: (value?: string) =>
          value ? (
            <Tag
              color={getTypeTagColor(value)}
              style={{ width: "fit-content" }}
            >
              {capitalizeWords(value)}
            </Tag>
          ) : (
            <span className="tcl-muted">—</span>
          ),
      },
      {
        title: "Priority",
        dataIndex: "priority",
        key: "priority",
        width: 60,
        render: (value?: string) =>
          value ? (
            <Tag
              color={getPriorityTagColor(value)}
              style={{ width: "fit-content" }}
            >
              {capitalizeWords(value)}
            </Tag>
          ) : (
            <span className="tcl-muted">—</span>
          ),
      },
      {
        title: "Format",
        dataIndex: "test_format_type",
        key: "test_format_type",
        width: 65,
        render: (value: TestCaseFormatType) => (
          <Tag
            color={getFormatTagColor(value)}
            style={{ width: "fit-content" }}
          >
            {formatFormatLabel(value)}
          </Tag>
        ),
      },
      {
        title: "Story",
        key: "story",
        width: 105,
        ellipsis: true,
        render: (_, record) => (
          <>
            <Tooltip title={record.storyTitle}>
              <span className="tcl-muted">{record.storyKey}</span>
              <span className="tcl-title-cell">{record.storyTitle}</span>
            </Tooltip>
          </>
        ),
      },
      {
        title: "Epic",
        key: "epic",
        width: 105,
        ellipsis: true,
        render: (_, record) => (
          <>
            <Tooltip title={record.epicTitle}>
              <span className="tcl-muted">{record.epicKey}</span>
              <span className="tcl-title-cell">{record.epicTitle}</span>
            </Tooltip>
          </>
        ),
      },
      {
        title: "Project",
        dataIndex: "projectName",
        key: "projectName",
        width: 100,
        ellipsis: true,
        render: (value: string) => (
          <Tooltip title={value}>
            <span className="tcl-title-cell">{value}</span>
          </Tooltip>
        ),
      },
      {
        title: "Created",
        dataIndex: "createdAt",
        key: "createdAt",
        width: 65,
        render: (value: string) => (
          <span className="tcl-muted">{formatRelativeTime(value)}</span>
        ),
      },
    ];

    return cols;
  }, []);

  // --- Table key: reset on project change without unmounting on keystrokes ---

  const tableKey = selectedProjectId ?? "no-project";
  const expandableRows = expandedId ? [expandedId] : [];

  // Bulk approval: count eligible selected rows
  const eligibleSelectedCount = selectedRowKeys.filter((key) =>
    selectableRowKeys.has(key),
  ).length;

  if (projectsError && projects.length === 0) {
    return (
      <div className="tcl-page tcl-state-page">
        <div className="tcl-error-state">
          <p className="tcl-error-title">Failed to load projects</p>
          <p className="tcl-error-text">{projectsError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tcl-page">
      <div className="tcl-content">
        <section className="tcl-summary" aria-label="Test case summary">
          {summaryItems.map((item) => (
            <div className="tcl-summary-item" key={item.label}>
              <p>{item.label}</p>
              <strong>{item.value}</strong>
              <span>{item.helper}</span>
            </div>
          ))}
        </section>

        <section className="tcl-filters" aria-label="Test case filters">
          <label className="tcl-search">
            <SearchOutlined />
            <input
              placeholder="Search by title, ID, tags..."
              type="search"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </label>

          <ConfigProvider theme={TCL_SELECT_THEME}>
            <Select
              aria-label="Project selector"
              className="tcl-select"
              style={{ width: 320 }}
              value={selectedProjectId ?? undefined}
              options={projectOptions}
              onChange={(value) => {
                setCurrentPage(1);
                setExpandedId("");
                setSelectedProjectId(value ?? null);
              }}
              showSearch
              optionFilterProp="label"
              loading={projectsLoading}
              disabled={projectsLoading || projectOptions.length === 0}
              placeholder={
                projectsLoading ? "Loading projects…" : "Select a project"
              }
              notFoundContent={
                projectsLoading ? <Spin size="small" /> : "No projects found"
              }
            />
            <Select
              aria-label="Approval status filter"
              className="tcl-select"
              value={approvalStatus}
              options={APPROVAL_STATUS_OPTIONS}
              onChange={(value: ApprovalStatusFilter) => {
                setCurrentPage(1);
                setExpandedId("");
                setSelectedRowKeys([]);
                setApprovalStatus(value);
              }}
            />
            <Select
              aria-label="Priority filter"
              className="tcl-select"
              value={filters.priority}
              options={filterOptions.priorities}
              onChange={(value) => updateFilter("priority", value)}
            />
            <Select
              aria-label="Format filter"
              className="tcl-select"
              value={filters.format}
              options={filterOptions.formats}
              onChange={(value) => updateFilter("format", value)}
            />
            <Select
              aria-label="Type filter"
              className="tcl-select"
              value={filters.type}
              options={filterOptions.types}
              onChange={(value) => updateFilter("type", value)}
            />
          </ConfigProvider>
        </section>

        {showRowSelection && (
          <div className="tcl-bulk-bar">
            <div className="tcl-bulk-left">
              {eligibleSelectedCount > 0 ? (
                <>
                  <span className="tcl-bulk-pill">
                    {eligibleSelectedCount} Selected
                  </span>
                  <span className="tcl-bulk-hint">
                    {eligibleSelectedCount === 1
                      ? "1 unapproved test case selected"
                      : `${eligibleSelectedCount} unapproved test cases selected`}
                  </span>
                </>
              ) : (
                <span className="tcl-bulk-hint">
                  Select test cases using checkboxes to approve
                </span>
              )}
            </div>

            <div className="tcl-bulk-right">
              {selectableOnCurrentPage.size > 0 &&
                Array.from(selectableOnCurrentPage).some(
                  (key) => !selectedRowKeys.includes(key),
                ) && (
                  <button
                    type="button"
                    className="tcl-bulk-btn tcl-bulk-btn--secondary"
                    onClick={() =>
                      setSelectedRowKeys((prev) =>
                        Array.from(
                          new Set([...prev, ...selectableOnCurrentPage]),
                        ),
                      )
                    }
                  >
                    Select all on page ({selectableOnCurrentPage.size})
                  </button>
                )}

              <Tooltip
                title={
                  eligibleSelectedCount === 0
                    ? "Select test cases using the checkboxes to approve."
                    : ""
                }
              >
                <span>
                  <button
                    type="button"
                    className="tcl-bulk-btn tcl-bulk-btn--primary"
                    disabled={eligibleSelectedCount === 0 || approving}
                    onClick={() =>
                      confirmApprove(
                        selectedRowKeys.filter((key) =>
                          selectableRowKeys.has(key),
                        ),
                      )
                    }
                  >
                    <CheckOutlined style={{ fontSize: 11 }} />
                    <span>
                      {eligibleSelectedCount > 0
                        ? `Approve Selected (${eligibleSelectedCount})`
                        : "Approve Selected"}
                    </span>
                  </button>
                </span>
              </Tooltip>

              {eligibleSelectedCount > 0 && (
                <button
                  type="button"
                  className="tcl-bulk-btn tcl-bulk-btn--ghost"
                  onClick={() => setSelectedRowKeys([])}
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        )}

        {projectsError && projects.length > 0 && (
          <div className="tcl-error-state tcl-inline-error">
            <p className="tcl-error-title">
              Project list loaded, but test cases failed
            </p>
            <p className="tcl-error-text">{projectsError}</p>
          </div>
        )}

        <div className="tcl-table-wrap">
          {projectsLoading || testCasesLoading ? (
            <div className="tcl-table-state">
              <span
                style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
              >
                <Spin size="medium" />
                <span>
                  {projectsLoading
                    ? "Loading projects..."
                    : `Loading test cases for ${
                        selectedProject?.name ?? "the selected project"
                      }...`}
                </span>
              </span>
            </div>
          ) : visibleTestCases.length === 0 ? (
            <div className="tcl-table-state">
              {testCasesError
                ? testCasesError
                : projectOptions.length === 0
                ? "No projects found."
                : "No test cases match the current search and filters."}
            </div>
          ) : (
            <AITable<TestCase>
              key={tableKey}
              rowKey="id"
              columns={testCaseColumns}
              datasource={paginatedTestCases}
              showPagination={false}
              rowSelection={rowSelection}
              rowClassName={(record) =>
                `tcl-data-row${
                  expandedId === record.id ? " tcl-data-row--expanded" : ""
                }`
              }
              expandable={{
                expandedRowKeys: expandableRows,
                expandRowByClick: true,
                showExpandColumn: false,
                onExpand: (expanded, record) => {
                  setExpandedId(expanded ? record.id : "");
                },
                expandedRowRender: (record) => (
                  <TestCaseDetails testCase={record} />
                ),
              }}
            />
          )}
        </div>

        {visibleTestCases.length > pageSize && (
          <div className="tcl-pagination-bar">
            <span className="tcl-pagination-summary">
              {paginationStart}-{paginationEnd} of {visibleTestCases.length}
            </span>

            <div className="tcl-pagination-center">
              <Pagination
                current={currentPage}
                total={visibleTestCases.length}
                pageSize={pageSize}
                showSizeChanger={false}
                onChange={(page) => {
                  setExpandedId("");
                  setCurrentPage(page);
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
