"use client";

import { Fragment, useMemo, useCallback, useState, useRef } from "react";
import { App, Tooltip } from "antd";
import {
  GenerationSettings,
  FlatTestCase,
  TestGeneratorResponseData,
  TestCaseStatus,
  TEST_CASE_FORMATS,
} from "@/types/testGenerator";
import {
  buildIssueStoryKeySet,
  buildIssueCards,
  toScenario,
  normalizePriority,
  toTextList,
  buildExportRows,
  downloadExcel,
} from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import { updateTestCaseStatus } from "@/services/testCaseService";
import {
  pushAllUserStoryTestCases,
  JiraNotConfiguredError,
} from "@/services/jiraService";
import JiraSVG from "../assets/JiraSVG";
import CustomTestCaseCard from "./CustomTestCaseCard";
import ExcelJS from "exceljs";
import { useAppDispatch, useAppSelector } from "@/store/store";
import {
  setTestCaseStatus,
  bulkSetTestCaseStatus,
  toggleExpandedTestId,
  setHasPushed,
} from "@/store/slices/testGenerationSlice";
import "../assets/css/outputPanel.css";

import type { PushToJiraResult } from "@/types/jira";
import PushToJiraModal from "./Pushtojiramodal";

/* ─── Helpers ─── */

const STATUS_ICON: Record<TestCaseStatus, string> = {
  approved: "✔",
  pending: "⏱",
  archived: "▤",
};

const TYPE_BADGE_CLASS: Record<string, string> = {
  Positive: "tg-badge-positive",
  Negative: "tg-badge-negative",
  Edge: "tg-badge-edge",
  "Edge-Case": "tg-badge-edge",
};

const PRIORITY_BADGE_CLASS: Record<string, string> = {
  High: "tg-badge-high",
  Medium: "tg-badge-medium",
  Low: "tg-badge-low",
};

function getDisplayId(tc: FlatTestCase): string {
  return tc.testCaseKey || tc.id;
}

function renderExpandContent(
  tc: FlatTestCase,
  isCustomFormat: boolean,
  isBddFormat: boolean,
  rawTestCaseMap: Map<string, Record<string, unknown>>,
  customFields: string[],
): React.ReactNode {
  if (isCustomFormat) {
    const raw = rawTestCaseMap.get(tc.id);
    if (raw) {
      return <CustomTestCaseCard testCase={raw} customFields={customFields} />;
    }
    return <span className="tg-expand-empty">No custom data available.</span>;
  }

  if (isBddFormat && tc.scenario) {
    return (
      <div className="tg-expand-bdd">
        {tc.scenario.given && tc.scenario.given.length > 0 && (
          <div className="tg-bdd-section">
            <strong className="tg-bdd-label">Given</strong>
            <ul className="tg-steps-list">
              {tc.scenario.given.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {tc.scenario.when && tc.scenario.when.length > 0 && (
          <div className="tg-bdd-section">
            <strong className="tg-bdd-label">When</strong>
            <ul className="tg-steps-list">
              {tc.scenario.when.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
        {tc.scenario.then && tc.scenario.then.length > 0 && (
          <div className="tg-bdd-section">
            <strong className="tg-bdd-label">Then</strong>
            <ul className="tg-steps-list">
              {tc.scenario.then.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  // Structured format
  return (
    <>
      {tc.steps && tc.steps.length > 0 && (
        <ol className="tg-steps-list-numbered">
          {tc.steps.map((step, i) => (
            <li key={i}>
              <span className="tg-step-num">{i + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      )}
      {tc.expectedResult && (
        <div className="tg-expected-result">
          <strong>Expected result:</strong> {tc.expectedResult}
        </div>
      )}
    </>
  );
}

function renderActionButtons(
  tc: FlatTestCase,
  status: TestCaseStatus,
  isPushed: boolean,
  onStatusChange: (testCaseId: string, newStatus: TestCaseStatus) => void,
): React.ReactNode {
  if (isPushed) {
    return (
      <div className="tg-actions-cell">
        <span
          className="tg-pushed-label"
          style={{ color: "#8c8c8c", fontSize: "12px", fontStyle: "italic" }}
        >
          Pushed
        </span>
      </div>
    );
  }

  if (status === "pending") {
    return (
      <div className="tg-actions-cell">
        <button
          className="tg-btn-approve-row"
          onClick={() => onStatusChange(tc.id, "approved")}
        >
          ✓ Approve
        </button>
        <button
          className="tg-btn-icon"
          title="Archive"
          onClick={() => onStatusChange(tc.id, "archived")}
        >
          ▤
        </button>
      </div>
    );
  }

  if (status === "approved") {
    return (
      <div className="tg-actions-cell">
        <button
          className="tg-btn-icon"
          title="Archive"
          onClick={() => onStatusChange(tc.id, "archived")}
        >
          ▤
        </button>
      </div>
    );
  }

  // archived
  return (
    <div className="tg-actions-cell">
      <button
        className="tg-btn-restore"
        onClick={() => onStatusChange(tc.id, "pending")}
      >
        Restore
      </button>
    </div>
  );
}

/* ─── Types ─── */

interface StoryTableGroup {
  storyKey: string;
  storySummary: string;
  epicKey: string;
  epicSummary: string;
  testCases: FlatTestCase[];
  rawTestCases: Record<string, unknown>[];
}

interface OutputPanelProps {
  generationSettings: GenerationSettings;
  generatedData: TestGeneratorResponseData | null;
  isJiraImport: boolean;
  disableJiraPush?: boolean;
}

/* ─── Component ─── */

export default function OutputPanel({
  generationSettings,
  generatedData,
  isJiraImport,
  disableJiraPush,
}: Readonly<OutputPanelProps>) {
  const { message, modal } = App.useApp();
  const dispatch = useAppDispatch();
  const { testCaseStatuses, expandedTestIds, hasPushed } = useAppSelector(
    (state) => state.testGeneration.outputState,
  );
  const projectId = useAppSelector(
    (state) => state.testGeneration.inputState.projectId,
  );

  // Story-level collapse/expand
  const [collapsedStoryKeys, setCollapsedStoryKeys] = useState<Set<string>>(
    () => new Set(),
  );

  const [pushedTestCaseIds, setPushedTestCaseIds] = useState<Set<string>>(
    () => new Set(),
  );

  const latestStatusRef = useRef<Record<string, TestCaseStatus | undefined>>(
    {},
  );
  const pendingPromisesRef = useRef<Record<string, Promise<any> | undefined>>(
    {},
  );

  const STORY_TC_SCROLL_THRESHOLD = 8;

  const [pushLoading, setPushLoading] = useState(false);
  const [pushResult, setPushResult] = useState<PushToJiraResult | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const isCustomFormat = generationSettings.format === TEST_CASE_FORMATS.CUSTOM;
  const isBddFormat = generationSettings.format === TEST_CASE_FORMATS.BDD;

  const customFields = useMemo(
    () => generatedData?.metadata?.customFields ?? [],
    [generatedData],
  );

  const hidePriority = generationSettings.priority === "Manual";

  /* ── Validation / Issues ── */

  const backendIssueCards = useMemo(
    () => buildIssueCards(generatedData),
    [generatedData],
  );
  const backendIssueStoryKeys = useMemo(
    () => buildIssueStoryKeySet(generatedData),
    [generatedData],
  );
  const issueCards = backendIssueCards;
  const issueStoryKeys = useMemo(
    () => new Set<string>(backendIssueStoryKeys),
    [backendIssueStoryKeys],
  );

  const allFlatTestCases = useMemo(() => {
    const flat: FlatTestCase[] = [];

    generatedData?.generatedTestCases.forEach((epic) => {
      epic.stories.forEach((story) => {
        if (issueStoryKeys.has(story.storyKey)) return;

        story.testCases.forEach((testCase) => {
          const tc = testCase as unknown as Record<string, unknown>;
          const rawTitle = testCase.title ?? tc.Title;
          const rawType = testCase.type ?? tc.Type;
          const rawPreconditions = testCase.preconditions ?? tc.Preconditions;
          const rawSteps = testCase.steps ?? tc.Steps;
          const rawExpectedResult =
            testCase.expectedResult ?? tc["Expected Result"];
          const rawTestData = testCase.testData ?? tc["Test Data"];
          const rawTags = testCase.tags ?? tc.Tags;
          const rawPriority = testCase.priority ?? tc.Priority;

          flat.push({
            ...testCase,
            id: testCase.testCaseId,
            title: typeof rawTitle === "string" ? rawTitle : "",
            type: typeof rawType === "string" ? rawType : undefined,
            storyId: story.storyKey,
            storyTitle: story.storySummary,
            epicId: epic.epicKey,
            epicTitle: epic.epicSummary,
            preconditions: toTextList(rawPreconditions),
            steps: toTextList(rawSteps),
            expectedResult:
              typeof rawExpectedResult === "string"
                ? rawExpectedResult
                : undefined,
            scenario: toScenario(testCase.scenario),
            testData:
              rawTestData && typeof rawTestData === "object"
                ? (rawTestData as Record<string, unknown>)
                : undefined,
            tags: toTextList(rawTags),
            priority: hidePriority ? undefined : normalizePriority(rawPriority),
            // Preserve testCaseKey for display
            testCaseKey: testCase.testCaseKey,
          } as FlatTestCase);
        });
      });
    });

    return flat;
  }, [generatedData, hidePriority, issueStoryKeys]);

  /* Raw test case map for custom format rendering */
  const rawTestCaseMap = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    if (!isCustomFormat) return map;

    generatedData?.generatedTestCases.forEach((epic) => {
      epic.stories.forEach((story) => {
        story.testCases.forEach((tc) => {
          map.set(tc.testCaseId, tc as unknown as Record<string, unknown>);
        });
      });
    });

    return map;
  }, [generatedData, isCustomFormat]);

  /* ── Story groups ── */

  const storyGroups = useMemo(() => {
    const groupMap = new Map<string, StoryTableGroup>();

    allFlatTestCases.forEach((tc) => {
      if (!groupMap.has(tc.storyId)) {
        groupMap.set(tc.storyId, {
          storyKey: tc.storyId,
          storySummary: tc.storyTitle,
          epicKey: tc.epicId,
          epicSummary: tc.epicTitle,
          testCases: [],
          rawTestCases: [],
        });
      }
      const group = groupMap.get(tc.storyId)!;
      group.testCases.push(tc);
      const raw = rawTestCaseMap.get(tc.id);
      if (raw) group.rawTestCases.push(raw);
    });

    return Array.from(groupMap.values());
  }, [allFlatTestCases, rawTestCaseMap]);

  /* ── Status helpers ── */

  const getStatus = useCallback(
    (testCaseId: string): TestCaseStatus =>
      testCaseStatuses[testCaseId] ?? "pending",
    [testCaseStatuses],
  );

  const approvedCount = useMemo(
    () =>
      allFlatTestCases.filter((tc) => getStatus(tc.id) === "approved").length,
    [allFlatTestCases, getStatus],
  );

  const archivedCount = useMemo(
    () =>
      allFlatTestCases.filter((tc) => getStatus(tc.id) === "archived").length,
    [allFlatTestCases, getStatus],
  );

  const pendingCount = allFlatTestCases.length - approvedCount - archivedCount;
  const nonArchivedCount = pendingCount + approvedCount;

  // Track eligible counts for bulk buttons (excluding pushed ones)
  const unpushedApprovedCount = useMemo(
    () =>
      allFlatTestCases.filter(
        (tc) =>
          getStatus(tc.id) === "approved" && !pushedTestCaseIds.has(tc.id),
      ).length,
    [allFlatTestCases, getStatus, pushedTestCaseIds],
  );

  const eligibleArchiveCount = useMemo(
    () =>
      allFlatTestCases.filter(
        (tc) =>
          getStatus(tc.id) !== "archived" && !pushedTestCaseIds.has(tc.id),
      ).length,
    [allFlatTestCases, getStatus, pushedTestCaseIds],
  );

  const eligibleRestoreCount = useMemo(
    () =>
      allFlatTestCases.filter(
        (tc) =>
          getStatus(tc.id) === "archived" && !pushedTestCaseIds.has(tc.id),
      ).length,
    [allFlatTestCases, getStatus, pushedTestCaseIds],
  );

  /* ── Status transition handlers (optimistic + API) ── */

  const handleStatusChange = useCallback(
    async (testCaseId: string, newStatus: TestCaseStatus) => {
      if (pushedTestCaseIds.has(testCaseId)) return;
      if (!projectId) {
        message.error("Select a project first.");
        return;
      }
      const prevStatus = getStatus(testCaseId);

      latestStatusRef.current[testCaseId] = newStatus;
      dispatch(setTestCaseStatus({ testCaseId, status: newStatus }));

      // Optimistic update of hasPushed to enable/disable button immediately
      if (newStatus === "approved" || prevStatus === "approved") {
        dispatch(setHasPushed(false));
      }

      const performUpdate = async () => {
        // Wait for any previous request for this test case to finish
        if (pendingPromisesRef.current[testCaseId]) {
          try {
            await pendingPromisesRef.current[testCaseId];
          } catch {
            // Ignore previous errors so this one can proceed
          }
        }

        // Only proceed if this is still the latest desired status
        if (latestStatusRef.current[testCaseId] !== newStatus) {
          return;
        }

        await updateTestCaseStatus([testCaseId], newStatus, projectId);
      };

      const promise = performUpdate();
      pendingPromisesRef.current[testCaseId] = promise;

      try {
        await promise;
        if (pendingPromisesRef.current[testCaseId] === promise) {
          delete pendingPromisesRef.current[testCaseId];
        }
      } catch (err) {
        if (pendingPromisesRef.current[testCaseId] === promise) {
          delete pendingPromisesRef.current[testCaseId];
        }

        // Only rollback if no newer status update has been requested
        if (latestStatusRef.current[testCaseId] === newStatus) {
          dispatch(setTestCaseStatus({ testCaseId, status: prevStatus }));
          message.error(
            err instanceof Error ? err.message : "Failed to update status",
          );
        }
      }
    },
    [dispatch, getStatus, message, projectId, pushedTestCaseIds],
  );

  const handleBulkApprove = useCallback(
    async (testCaseIds: string[]) => {
      const pendingIds = testCaseIds.filter(
        (id) => getStatus(id) === "pending" && !pushedTestCaseIds.has(id),
      );
      if (pendingIds.length === 0) return;
      if (!projectId) {
        message.error("Select a project first.");
        return;
      }

      const prevStatuses = pendingIds.map((id) => ({
        id,
        status: getStatus(id),
      }));

      pendingIds.forEach((id) => {
        latestStatusRef.current[id] = "approved";
      });

      dispatch(
        bulkSetTestCaseStatus({ testCaseIds: pendingIds, status: "approved" }),
      );

      // Optimistic update of hasPushed
      dispatch(setHasPushed(false));

      const performBulkUpdate = async () => {
        await Promise.all(
          pendingIds.map(async (id) => {
            if (pendingPromisesRef.current[id]) {
              try {
                await pendingPromisesRef.current[id];
              } catch {}
            }
          }),
        );

        const targetIds = pendingIds.filter(
          (id) => latestStatusRef.current[id] === "approved",
        );
        if (targetIds.length === 0) return;

        await updateTestCaseStatus(targetIds, "approved", projectId);
      };

      const bulkPromise = performBulkUpdate();
      pendingIds.forEach((id) => {
        pendingPromisesRef.current[id] = bulkPromise;
      });

      try {
        await bulkPromise;
      } catch (err) {
        prevStatuses.forEach(({ id, status }) => {
          if (latestStatusRef.current[id] === "approved") {
            dispatch(setTestCaseStatus({ testCaseId: id, status }));
          }
        });
        message.error(
          err instanceof Error ? err.message : "Failed to approve test cases",
        );
      } finally {
        pendingIds.forEach((id) => {
          if (pendingPromisesRef.current[id] === bulkPromise) {
            delete pendingPromisesRef.current[id];
          }
        });
      }
    },
    [dispatch, getStatus, message, projectId, pushedTestCaseIds],
  );

  const handleBulkArchive = useCallback(
    async (testCaseIds: string[]) => {
      const nonArchivedIds = testCaseIds.filter(
        (id) => getStatus(id) !== "archived" && !pushedTestCaseIds.has(id),
      );
      if (nonArchivedIds.length === 0) return;
      if (!projectId) {
        message.error("Select a project first.");
        return;
      }

      const prevStatuses = nonArchivedIds.map((id) => ({
        id,
        status: getStatus(id),
      }));

      nonArchivedIds.forEach((id) => {
        latestStatusRef.current[id] = "archived";
      });

      dispatch(
        bulkSetTestCaseStatus({
          testCaseIds: nonArchivedIds,
          status: "archived",
        }),
      );

      const performBulkUpdate = async () => {
        await Promise.all(
          nonArchivedIds.map(async (id) => {
            if (pendingPromisesRef.current[id]) {
              try {
                await pendingPromisesRef.current[id];
              } catch {}
            }
          }),
        );

        const targetIds = nonArchivedIds.filter(
          (id) => latestStatusRef.current[id] === "archived",
        );
        if (targetIds.length === 0) return;

        await updateTestCaseStatus(targetIds, "archived", projectId);
      };

      const bulkPromise = performBulkUpdate();
      nonArchivedIds.forEach((id) => {
        pendingPromisesRef.current[id] = bulkPromise;
      });

      try {
        await bulkPromise;
      } catch (err) {
        prevStatuses.forEach(({ id, status }) => {
          if (latestStatusRef.current[id] === "archived") {
            dispatch(setTestCaseStatus({ testCaseId: id, status }));
          }
        });
        message.error(
          err instanceof Error ? err.message : "Failed to archive test cases",
        );
      } finally {
        nonArchivedIds.forEach((id) => {
          if (pendingPromisesRef.current[id] === bulkPromise) {
            delete pendingPromisesRef.current[id];
          }
        });
      }
    },
    [dispatch, getStatus, message, projectId, pushedTestCaseIds],
  );

  const handleBulkRestore = useCallback(
    async (testCaseIds: string[]) => {
      const archivedIds = testCaseIds.filter(
        (id) => getStatus(id) === "archived" && !pushedTestCaseIds.has(id),
      );
      if (archivedIds.length === 0) return;
      if (!projectId) {
        message.error("Select a project first.");
        return;
      }

      const prevStatuses = archivedIds.map((id) => ({
        id,
        status: getStatus(id),
      }));

      archivedIds.forEach((id) => {
        latestStatusRef.current[id] = "pending";
      });

      dispatch(
        bulkSetTestCaseStatus({
          testCaseIds: archivedIds,
          status: "pending",
        }),
      );

      const performBulkUpdate = async () => {
        await Promise.all(
          archivedIds.map(async (id) => {
            if (pendingPromisesRef.current[id]) {
              try {
                await pendingPromisesRef.current[id];
              } catch {}
            }
          }),
        );

        const targetIds = archivedIds.filter(
          (id) => latestStatusRef.current[id] === "pending",
        );
        if (targetIds.length === 0) return;

        await updateTestCaseStatus(targetIds, "pending", projectId);
      };

      const bulkPromise = performBulkUpdate();
      archivedIds.forEach((id) => {
        pendingPromisesRef.current[id] = bulkPromise;
      });

      try {
        await bulkPromise;
      } catch (err) {
        prevStatuses.forEach(({ id, status }) => {
          if (latestStatusRef.current[id] === "pending") {
            dispatch(setTestCaseStatus({ testCaseId: id, status }));
          }
        });
        message.error(
          err instanceof Error ? err.message : "Failed to restore test cases",
        );
      } finally {
        archivedIds.forEach((id) => {
          if (pendingPromisesRef.current[id] === bulkPromise) {
            delete pendingPromisesRef.current[id];
          }
        });
      }
    },
    [dispatch, getStatus, message, projectId, pushedTestCaseIds],
  );

  /* ── Expand toggle (test case) ── */

  const handleToggleExpand = useCallback(
    (testCaseId: string) => {
      dispatch(toggleExpandedTestId(testCaseId));
    },
    [dispatch],
  );

  /* ── Story-level collapse toggle ── */

  const handleToggleStoryCollapse = useCallback((storyKey: string) => {
    setCollapsedStoryKeys((prev) => {
      const next = new Set(prev);
      if (next.has(storyKey)) next.delete(storyKey);
      else next.add(storyKey);
      return next;
    });
  }, []);

  /* ── Export Excel ── */

  const exportApprovedToXlsx = useCallback(async () => {
    const approvedCases = allFlatTestCases.filter(
      (tc) => getStatus(tc.id) === "approved",
    );

    if (approvedCases.length === 0) {
      message.info("Approve test cases first");
      return;
    }

    try {
      const rows = buildExportRows(
        approvedCases,
        generationSettings.format,
        isCustomFormat ? customFields : undefined,
      );

      const workbook = new ExcelJS.Workbook();
      const worksheet = workbook.addWorksheet("Approved Test Cases");
      if (rows.length > 0) {
        worksheet.columns = Object.keys(rows[0]).map((key) => ({
          header: key,
          key,
        }));
        rows.forEach((row) => {
          worksheet.addRow(row);
        });
      }

      const buffer = await workbook.xlsx.writeBuffer();

      const blob = new Blob([buffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const fileName = `approved-test-cases-${new Date()
        .toISOString()
        .slice(0, 10)}.xlsx`;

      downloadExcel(blob, fileName);

      message.success(
        `Exported ${approvedCases.length} approved test case(s).`,
      );
    } catch (err) {
      message.error(
        err instanceof Error
          ? `Export failed: ${err.message}`
          : "Export failed. Please try again.",
      );
    }
  }, [
    allFlatTestCases,
    getStatus,
    generationSettings.format,
    isCustomFormat,
    customFields,
    message,
  ]);

  /* ── Push to Jira ── */

  const handlePushToJira = useCallback(async () => {
    const approvedCases = allFlatTestCases.filter(
      (tc) => getStatus(tc.id) === "approved" && !pushedTestCaseIds.has(tc.id),
    );
    if (approvedCases.length === 0) return;

    if (!projectId) {
      message.error("Select a project first.");
      return;
    }

    setPushLoading(true);
    setModalOpen(true);

    try {
      const result = await pushAllUserStoryTestCases(
        projectId,
        approvedCases,
        generationSettings.format,
      );

      setPushResult(result);
      const totalAttempted = approvedCases.length;
      const allDuplicated =
        result.pushed_count === 0 && result.duplicate_count === totalAttempted;
      if (result.pushed_count > 0 || allDuplicated) {
        dispatch(setHasPushed(true));

        setPushedTestCaseIds((prev) => {
          const next = new Set(prev);
          result.pushed.forEach((p) => {
            if (p.status === "pushed" || p.status === "duplicate") {
              const matchedCase = approvedCases.find(
                (tc) => tc.testCaseKey === p.tc_id || tc.id === p.tc_id,
              );
              if (matchedCase) {
                next.add(matchedCase.id);
              } else {
                next.add(p.tc_id);
              }
            }
          });
          return next;
        });
      } else {
        dispatch(setHasPushed(false));
      }

      modal.success({
        title: "Push to Jira Successful",
        content: (
          <div>
            <p>{result.pushed_count} test case(s) pushed to Jira.</p>
            {result.pushed.length > 0 && (
              <p>
                Jira keys:{" "}
                {result.pushed
                  .map((p) => p.jira_key)
                  .filter(Boolean)
                  .join(", ")}
              </p>
            )}
            <p>
              {result.duplicate_count > 0
                ? `${result.duplicate_count} duplicate(s) skipped.`
                : ""}
            </p>
            <p>
              {result.failed_count > 0 ? `${result.failed_count} failed.` : ""}
            </p>
          </div>
        ),
      });
    } catch (err) {
      if (err instanceof JiraNotConfiguredError) {
        modal.error({
          title: "Jira credentials not set up",
          content: err.message,
        });
      } else {
        message.error(
          err instanceof Error ? err.message : "Push to Jira failed",
        );
      }
      setModalOpen(false);
    } finally {
      setPushLoading(false);
    }
  }, [
    allFlatTestCases,
    getStatus,
    generationSettings.format,
    dispatch,
    modal,
    message,
    pushedTestCaseIds,
    projectId,
  ]);

  /* ── Push to ADO (UI-only placeholder) ── */
  // TODO: Implement actual ADO push logic when backend is ready
  // const handlePushToAdo = useCallback(() => {
  //   message.info("Push to ADO — coming soon");
  // }, [message]);

  const jiraPushTitle = !isJiraImport
    ? "Only available when stories are imported from Jira"
    : disableJiraPush
    ? "Disabled — re-import from Jira to enable"
    : approvedCount === 0
    ? "Approve test cases first"
    : unpushedApprovedCount === 0
    ? "Already pushed — approve more test cases to push again"
    : undefined;

  /* ─── JSX ─── */

  return (
    <div className="tg-output-root">
      {/* Summary Strip */}
      <div className="tg-summary">
        <div className="tg-sum-box">
          <div className="tg-sum-count">{allFlatTestCases.length}</div>
          <div className="tg-sum-label">Generated</div>
        </div>
        <div className="tg-sum-box tg-sum-green">
          <div className="tg-sum-count">{approvedCount}</div>
          <div className="tg-sum-label">Approved</div>
        </div>
        <div className="tg-sum-box tg-sum-grey">
          <div className="tg-sum-count">{archivedCount}</div>
          <div className="tg-sum-label">Archived</div>
        </div>
        <div className="tg-sum-box tg-sum-amber">
          <div className="tg-sum-count">{pendingCount}</div>
          <div className="tg-sum-label">Pending</div>
        </div>
      </div>

      {/* Global Pending Actions */}
      <div className="tg-global-actions-bar">
        <div className="tg-global-actions">
          <button
            type="button"
            className="tg-btn tg-btn-approve-outline"
            disabled={pendingCount === 0}
            onClick={() =>
              handleBulkApprove(allFlatTestCases.map((tc) => tc.id))
            }
          >
            ✓ Approve All Pending Test Cases
          </button>
          <button
            type="button"
            className="tg-btn tg-btn-archive-outline"
            disabled={eligibleArchiveCount === 0}
            onClick={() =>
              handleBulkArchive(
                allFlatTestCases
                  .filter(
                    (tc) =>
                      getStatus(tc.id) !== "archived" &&
                      !pushedTestCaseIds.has(tc.id),
                  )
                  .map((tc) => tc.id),
              )
            }
          >
            ⊘ Archive All Pending/Approved Test Cases
          </button>

          <button
            type="button"
            className="tg-btn tg-btn-restore-outline"
            disabled={eligibleRestoreCount === 0}
            onClick={() =>
              handleBulkRestore(
                allFlatTestCases
                  .filter(
                    (tc) =>
                      getStatus(tc.id) === "archived" &&
                      !pushedTestCaseIds.has(tc.id),
                  )
                  .map((tc) => tc.id),
              )
            }
          >
            ↩ Restore All Archived Test Cases
          </button>
        </div>
      </div>

      {/* Scrollable story tables */}
      <div className="tg-output-scroll">
        {/* Issue Cards (unsuccessful stories) */}
        {issueCards.length > 0 && (
          <div className="tg-issue-card-list">
            {issueCards.map((issue) => (
              <div key={issue.id} className="tg-issue-card">
                <div className="tg-issue-card-header-row">
                  <span className="tg-issue-card-status">
                    Unsuccessful Story
                  </span>
                  <span className="tg-issue-card-meta">
                    {issue.epicKey && <span>{issue.epicKey}</span>}
                    {issue.storyKey && <span>{issue.storyKey}</span>}
                  </span>
                </div>
                <div className="tg-issue-card-message">{issue.message}</div>
              </div>
            ))}
          </div>
        )}

        {storyGroups.map((group) => {
          const groupTcIds = group.testCases.map((tc) => tc.id);
          const pendingInGroup = groupTcIds.filter(
            (id) => getStatus(id) === "pending" && !pushedTestCaseIds.has(id),
          );
          const nonArchivedInGroup = groupTcIds.filter(
            (id) => getStatus(id) !== "archived" && !pushedTestCaseIds.has(id),
          );
          const archivedInGroup = groupTcIds.filter(
            (id) => getStatus(id) === "archived" && !pushedTestCaseIds.has(id),
          );

          const isCollapsed = collapsedStoryKeys.has(group.storyKey);
          const shouldScrollStoryTable =
            group.testCases.length > STORY_TC_SCROLL_THRESHOLD;

          return (
            <div key={group.storyKey} className="tg-story-table-card">
              {/* Bulk bar + story collapse toggle */}
              <div className="tg-bulk-bar">
                <button
                  type="button"
                  className={`tg-story-collapse-toggle${
                    isCollapsed ? " collapsed" : ""
                  }`}
                  onClick={() => handleToggleStoryCollapse(group.storyKey)}
                  aria-expanded={!isCollapsed}
                >
                  <span className="tg-story-collapse-chevron">›</span>
                </button>

                <span className="tg-story-ctx">
                  <span className="tg-story-ctx-text">
                    <strong>{group.storyKey}</strong> — {group.storySummary}
                  </span>
                  <span className="tg-story-ctx-count">
                    · {group.testCases.length} test cases
                  </span>
                </span>

                <div className="tg-bulk-actions">
                  <button
                    className="tg-btn tg-btn-approve-outline"
                    disabled={pendingInGroup.length === 0}
                    onClick={() => handleBulkApprove(groupTcIds)}
                  >
                    ✓ Approve Pending Test Cases
                  </button>
                  <button
                    className="tg-btn tg-btn-archive-outline"
                    disabled={nonArchivedInGroup.length === 0}
                    onClick={() => handleBulkArchive(nonArchivedInGroup)}
                  >
                    ⊘ Archive Pending/Approved Test Cases
                  </button>

                  <button
                    className="tg-btn tg-btn-restore-outline"
                    disabled={archivedInGroup.length === 0}
                    onClick={() => handleBulkRestore(archivedInGroup)}
                  >
                    ↩ Restore Archived Test Cases
                  </button>
                </div>
              </div>

              {/* Table (conditionally rendered) */}
              {!isCollapsed && (
                <div
                  className={`tg-story-table-wrap${
                    shouldScrollStoryTable ? " tg-story-table-scroll" : ""
                  }`}
                >
                  <div className="tg-grid">
                    {/* Header — always render all 7 columns for alignment */}
                    <div className="tg-grid-header">
                      <div className="tg-grid-cell"></div>
                      <div className="tg-grid-cell">TC ID</div>
                      <div className="tg-grid-cell">Title</div>
                      <div
                        className={`tg-grid-cell${
                          isCustomFormat ? " tg-grid-cell-hidden" : ""
                        }`}
                      >
                        Type
                      </div>
                      <div
                        className={`tg-grid-cell${
                          !hidePriority && !isCustomFormat
                            ? ""
                            : " tg-grid-cell-hidden"
                        }`}
                      >
                        Priority
                      </div>
                      <div className="tg-grid-cell">Status</div>
                      <div className="tg-grid-cell">Actions</div>
                    </div>

                    {/* Rows */}
                    {group.testCases.map((tc) => {
                      const status = getStatus(tc.id);
                      const isExpanded = !!expandedTestIds[tc.id];

                      return (
                        <Fragment key={tc.id}>
                          <div className={`tg-grid-row tg-row-${status}`}>
                            <div className="tg-grid-cell tg-grid-cell-expand">
                              <button
                                className={`tg-chevron-btn${
                                  isExpanded ? " open" : ""
                                }`}
                                onClick={() => handleToggleExpand(tc.id)}
                              >
                                ›
                              </button>
                            </div>
                            <div className="tg-grid-cell tg-grid-cell-tcid">
                              {getDisplayId(tc)}
                            </div>
                            <div className="tg-grid-cell tg-grid-cell-title">
                              {tc.title}
                            </div>
                            {/* Type column — always rendered, hidden when not applicable */}
                            <div
                              className={`tg-grid-cell${
                                isCustomFormat ? " tg-grid-cell-hidden" : ""
                              }`}
                            >
                              {!isCustomFormat && tc.type && (
                                <span
                                  className={`tg-badge ${
                                    TYPE_BADGE_CLASS[tc.type] ??
                                    "tg-badge-default"
                                  }`}
                                >
                                  {tc.type}
                                </span>
                              )}
                            </div>
                            {/* Priority column — always rendered, hidden when not applicable */}
                            <div
                              className={`tg-grid-cell${
                                !hidePriority && !isCustomFormat
                                  ? ""
                                  : " tg-grid-cell-hidden"
                              }`}
                            >
                              {!hidePriority &&
                                !isCustomFormat &&
                                tc.priority && (
                                  <span
                                    className={`tg-badge ${
                                      PRIORITY_BADGE_CLASS[tc.priority] ??
                                      "tg-badge-default"
                                    }`}
                                  >
                                    {tc.priority}
                                  </span>
                                )}
                            </div>
                            <div className="tg-grid-cell">
                              <span className={`tg-badge tg-badge-${status}`}>
                                {STATUS_ICON[status]}{" "}
                                {status.charAt(0).toUpperCase() +
                                  status.slice(1)}
                              </span>
                            </div>
                            <div className="tg-grid-cell">
                              {renderActionButtons(
                                tc,
                                status,
                                pushedTestCaseIds.has(tc.id),
                                handleStatusChange,
                              )}
                            </div>
                          </div>
                          {isExpanded && (
                            <div
                              className="tg-grid-expand-row"
                              key={`${tc.id}-expand`}
                            >
                              <div className="tg-expand-content">
                                {renderExpandContent(
                                  tc,
                                  isCustomFormat,
                                  isBddFormat,
                                  rawTestCaseMap,
                                  customFields,
                                )}
                              </div>
                            </div>
                          )}
                        </Fragment>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Export Bar */}
      <div className="tg-export-bar">
        <span
          className={`tg-export-label ${
            approvedCount > 0 ? "has-approved" : "none-approved"
          }`}
        >
          {approvedCount} test case{approvedCount !== 1 ? "s" : ""} approved —
          ready to export
        </span>
        <div className="tg-export-btns">
          <button
            className={`tg-btn-export ${
              approvedCount > 0 ? "enabled" : "disabled"
            }`}
            disabled={approvedCount === 0}
            onClick={exportApprovedToXlsx}
          >
            Export Excel
          </button>
          <Tooltip title={jiraPushTitle}>
            <span style={{ display: "inline-flex" }}>
              <button
                className={`tg-btn-export ${
                  !isJiraImport ||
                  unpushedApprovedCount === 0 ||
                  pushLoading ||
                  !!disableJiraPush
                    ? "disabled"
                    : "enabled"
                }`}
                disabled={
                  !isJiraImport ||
                  unpushedApprovedCount === 0 ||
                  pushLoading ||
                  !!disableJiraPush
                }
                onClick={handlePushToJira}
                style={{
                  pointerEvents:
                    !isJiraImport ||
                    unpushedApprovedCount === 0 ||
                    pushLoading ||
                    !!disableJiraPush
                      ? "none"
                      : "auto",
                }}
              >
                <JiraSVG /> {pushLoading ? "Pushing..." : "Push to Jira"}
              </button>
            </span>
          </Tooltip>
          <button
            className={`tg-btn-export ${
              approvedCount > 0 ? "enabled" : "disabled"
            }`}
            disabled={approvedCount === 0}
            //TODO: Implement actual ADO push logic when backend is ready
            // onClick={handlePushToAdo}
          >
            Push to ADO
          </button>
        </div>
      </div>

      {/* Push to Jira Modal */}
      <PushToJiraModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        result={pushResult}
        loading={pushLoading}
      />
    </div>
  );
}
