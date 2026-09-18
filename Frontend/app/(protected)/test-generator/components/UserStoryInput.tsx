"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/store";
import {
  clearTestGenerationState,
  setUploadedFiles,
  setProjectId,
  // Aliased: `setTableData` is also the name of this component's prop.
  setTableData as setTableDataAction,
} from "@/store/slices/testGenerationSlice";
import { App, Modal, Select, Spin, ConfigProvider, Upload } from "antd";
import type { UploadProps } from "antd";
import { EpicGroup, ExcelRow } from "@/types/testGenerator";
import ExcelJS from "exceljs";
import {
  initializeUniversitySanitizer,
  sanitizeEpicsPayload,
} from "@/utils/sanitizer/pipeline";
import { normalizePriority } from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import "../assets/css/UserStoryInput.css";
import type { DisplayStory, JiraEpic, RefreshResult } from "@/types/jira";
import {
  fetchAllFromJira,
  refreshFromJira,
  getJiraStatuses,
  JiraNotConfiguredError,
} from "@/services/jiraService";
import { applyRefreshChanges } from "@/services/jiraService";
import { parseCSV } from "@/utils/csvParser";
import { fetchStoryStatuses } from "@/services/databaseService";
import JiraSVG from "../assets/JiraSVG";
import ExcelSVG from "../assets/ExcelSVG";
import JiraTabPanel from "./JiraTabPanel";
import ExcelTabPanel from "./ExcelTabPanel";
import { BackendProject } from "@/types/project";
import { fetchProjects } from "@/services/projectService";

type ImportTab = "jira" | "excel" | "ado";
const projectOptionLabel = (p: BackendProject) =>
  `${p.client_name} - ${p.programme_name} - ${p.name}`;

interface UserStoryInputProps {
  isFileUploaded: boolean;
  hasSavedToDb: boolean;
  isJiraImport: boolean;
  setIsJiraImport: (value: boolean) => void;
  onFileUploaded: () => void;
  onFileRemoved: () => void;
  onMarkPasteOrUpload?: (value: boolean) => void;
  setTableData: (data: EpicGroup[]) => void;
  tableData: EpicGroup[];
  onRefreshChanged?: (changedKeys: string[]) => void;
  onNewStoriesDetected?: (keys: string[]) => void;
  onProjectSelected?: (project: BackendProject | null) => void;
  onImportLoadingChange?: (loading: boolean) => void;
}

export default function UserStoryInput({
  isFileUploaded,
  isJiraImport,
  setIsJiraImport,
  onFileUploaded,
  onFileRemoved,
  onMarkPasteOrUpload,
  setTableData,
  tableData,
  onRefreshChanged,
  onNewStoriesDetected,
  onProjectSelected,
  onImportLoadingChange,
}: UserStoryInputProps) {
  const { message, modal } = App.useApp();
  const messageRef = useRef(message);
  useEffect(() => {
    messageRef.current = message;
  }, [message]);

  const [projects, setProjects] = useState<BackendProject[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ImportTab>("jira");
  const dispatch = useAppDispatch();
  const reduxProjectId = useAppSelector(
    (state) => state.testGeneration.inputState.projectId,
  );

  const selectedProject = useMemo(() => {
    if (projects.length === 0) return null;
    const firstId = projects[0]?.id ? String(projects[0].id) : null;
    const reduxId = reduxProjectId ? String(reduxProjectId) : null;
    const isReduxIdAvailable = reduxId
      ? projects.some((p) => String(p.id) === reduxId)
      : false;
    return isReduxIdAvailable ? reduxId : firstId;
  }, [projects, reduxProjectId]);

  useEffect(() => {
    if (!selectedProject) return;
    if (reduxProjectId && String(reduxProjectId) === selectedProject) return;
    dispatch(setProjectId(selectedProject));
  }, [selectedProject, reduxProjectId, dispatch]);

  useEffect(() => {
    let cancelled = false;
    void fetchProjects()
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch((err) => {
        if (cancelled) return;
        messageRef.current.error(
          err instanceof Error
            ? `${err.message}`
            : "Could not load projects. Please refresh the page.",
        );
      })
      .finally(() => {
        if (!cancelled) setProjectsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const projectOptions = projects.map((p) => ({
    value: String(p.id),
    label: projectOptionLabel(p),
  }));

  useEffect(() => {
    if (!onProjectSelected) return;
    const found = selectedProject
      ? projects.find((p) => String(p.id) === selectedProject) ?? null
      : null;
    onProjectSelected(found);
  }, [selectedProject, projects, onProjectSelected]);

  const [jiraLoading, setJiraLoading] = useState(false);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [refreshModalOpen, setRefreshModalOpen] = useState(false);
  const [refreshResult, setRefreshResult] = useState<RefreshResult | null>(
    null,
  );
  const [fetchedStoriesAndEpics, setFetchedStoriesAndEpics] = useState<{
    stories: DisplayStory[];
    epics: JiraEpic[];
  } | null>(null);
  // Refreshed Jira content, staged until the user clicks "Apply Changes".
  const pendingRefreshRef = useRef<{
    stories: DisplayStory[];
    epics: JiraEpic[];
    tableData: EpicGroup[];
    changedStoryKeys: string[];
    newStoryIds: string[];
  } | null>(null);
  // Guard: suppress the window-focus status enrichment for a short window after
  // applying a Jira refresh so the enrichment effect doesn't race with / overwrite
  // the freshly applied table data.
  const refreshJustAppliedRef = useRef(false);

  const [hasJiraImported, setHasJiraImported] = useState(false);
  const [frontendNewStories, setFrontendNewStories] = useState<string[]>([]);
  const [jiraStatuses, setJiraStatuses] = useState<string[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [statusesLoading, setStatusesLoading] = useState(true);
  const fileList = useAppSelector(
    (state) => state.testGeneration.inputState.uploadedFiles,
  );

  // Excel/CSV stories are parsed client-side, so unlike Jira they miss the backend
  // status enrichment. Look up existing DB status by story key and merge it in, so
  // already-approved / rejected / in-review stories are badged (and blocked) the same.
  const enrichEpicsWithStatuses = useCallback(
    async (epics: EpicGroup[]): Promise<EpicGroup[]> => {
      if (!selectedProject) return epics;
      const storyKeys = epics.flatMap((e) => e.stories.map((s) => s.storyId));
      try {
        const statuses = await fetchStoryStatuses(selectedProject, storyKeys);
        return epics.map((epic) => ({
          ...epic,
          stories: epic.stories.map((story) => {
            const meta = statuses[story.storyId];
            return meta
              ? {
                  ...story,
                  status: meta.status,
                  alreadyExists: meta.already_exists,
                }
              : story;
          }),
        }));
      } catch (err) {
        // Best-effort: a lookup failure must not block the import, but surface it in
        // dev so a 401/403/404 (e.g. backend not restarted) isn't silently hidden.
        console.warn("Excel import: story status enrichment failed", err);
        return epics;
      }
    },
    [selectedProject],
  );

  // A reviewer's decision lands in the database, not in this tab — so without
  // this the only way to see an approval was to re-import. Re-read the statuses
  // on mount (covers navigating back to this page, which never fires `focus`)
  // and on every window focus (covers the tab being left open). Same enrichment
  // the import path uses, so it only touches `status`/`alreadyExists` and inline
  // edits survive. Dispatches only on an actual change, so neither idle tab-
  // switching nor an unrelated edit re-renders the table.
  const storyTableData = useAppSelector(
    (state) => state.testGeneration.inputState.tableData,
  );
  const refreshedOnMount = useRef(false);
  useEffect(() => {
    if (!selectedProject || storyTableData.length === 0) return;

    const refresh = async () => {
      // Skip the enrichment if a Jira refresh was just applied — the data in
      // Redux is already fresh and an async enrichment call could overwrite it
      // with stale DB-status results before the new data has rendered.
      if (refreshJustAppliedRef.current) return;
      const enriched = await enrichEpicsWithStatuses(storyTableData);
      // Re-check after the async gap: another refresh may have landed while
      // the enrichment request was in flight.
      if (refreshJustAppliedRef.current) return;
      const changed = enriched.some((epic, i) =>
        epic.stories.some((story, j) => {
          const before = storyTableData[i]?.stories[j];
          if (!before) return true;
          return (
            story.status !== before.status ||
            story.alreadyExists !== before.alreadyExists
          );
        }),
      );
      if (changed) dispatch(setTableDataAction(enriched));
    };

    // Once per mount, on the first render that actually has stories to check —
    // the effect also re-runs on every edit to `storyTableData`, which must not
    // trigger a lookup.
    if (!refreshedOnMount.current) {
      refreshedOnMount.current = true;
      void refresh();
    }

    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [selectedProject, storyTableData, enrichEpicsWithStatuses, dispatch]);
  useEffect(() => {
    if (!selectedProject) return;
    let cancelled = false;
    getJiraStatuses(selectedProject)
      .then((statuses) => {
        if (!cancelled) setJiraStatuses(statuses);
      })
      .catch((err) => {
        if (cancelled) return;
        setJiraStatuses([]);
        // Unconfigured projects surface a clearer modal on import; stay quiet here.
        if (err instanceof JiraNotConfiguredError) return;
        messageRef.current.warning(
          err instanceof Error
            ? err.message
            : "Couldn't load Jira statuses — status filter unavailable.",
        );
      })
      .finally(() => {
        if (!cancelled) setStatusesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProject]);

  const readData = async (file: File) => {
    const isCSV =
      file.type === "text/csv" || file.name.toLowerCase().endsWith(".csv");

    let rows: Record<string, unknown>[];

    if (isCSV) {
      const text = await file.text();
      rows = parseCSV(text) as Record<string, unknown>[];
    } else {
      const data = await file.arrayBuffer();
      const workbook = new ExcelJS.Workbook();
      await workbook.xlsx.load(data);
      const worksheet = workbook.worksheets[0];
      if (!worksheet) {
        message.error("The uploaded file contains no worksheets.");
        return;
      }

      const headers: string[] = [];
      const xlsxRows: Record<string, unknown>[] = [];
      worksheet.getRow(1).eachCell((cell, colNumber) => {
        headers[colNumber - 1] = String(cell.value ?? "");
      });
      worksheet.eachRow((row, rowNumber) => {
        if (rowNumber === 1) return;
        const rowData: Record<string, unknown> = {};
        row.eachCell((cell, colNumber) => {
          rowData[headers[colNumber - 1]] = cell.value;
        });
        xlsxRows.push(rowData);
      });
      rows = xlsxRows;
    }

    if (rows.length === 0) {
      message.error("The uploaded file contains no data rows.");
      return;
    }

    const REQUIRED_COLUMNS = [
      "Epic_ID",
      "Epic_Title",
      "Story_ID",
      "Story_Title",
      "Description",
      "Priority",
      "Acceptance_Criteria",
    ] as const;

    const presentColumns = new Set(Object.keys(rows[0]));
    const missingColumns = REQUIRED_COLUMNS.filter(
      (col) => !presentColumns.has(col),
    );
    if (missingColumns.length > 0) {
      message.error(
        `Missing required columns: ${missingColumns.join(", ")}. ` +
          "Column names must match exactly - see the Required columns listed in the upload panel.",
      );
      return;
    }

    const jsonData = rows as unknown as ExcelRow[];
    const groupedData: Record<string, EpicGroup> = {};

    jsonData.forEach((row: ExcelRow) => {
      const epicId = row.Epic_ID;
      const epicTitle = row.Epic_Title;
      if (!groupedData[epicId]) {
        groupedData[epicId] = { epicId, epicTitle, stories: [] };
      }
      groupedData[epicId].stories.push({
        storyId: row["Story_ID"],
        epicId,
        storyTitle: row["Story_Title"],
        description: row["Description"],
        priority: row["Priority"],
        acceptanceCriteria: row["Acceptance_Criteria"]
          ? row["Acceptance_Criteria"].split("\n")
          : [],
      });
    });
    const epics = Object.values(groupedData);

    try {
      initializeUniversitySanitizer();
      const payloadToSanitize = epics.map((epic) => ({ [epic.epicId]: epic }));
      const sanitizedPayload = sanitizeEpicsPayload(payloadToSanitize);
      const sanitizedEpics = sanitizedPayload.map(
        (entry) => Object.values(entry)[0],
      ) as EpicGroup[];
      await setTableData(await enrichEpicsWithStatuses(sanitizedEpics));
    } catch {
      message.warning(
        "Some data could not be sanitized. Imported with raw values.",
      );
    }
  };

  const handleJiraImport = async () => {
    if (!selectedProject) {
      message.error("Select a project first.");
      return;
    }
    try {
      setJiraLoading(true);

      const data = await fetchAllFromJira(selectedProject, selectedStatuses);
      const { stories, epics } = data;
      setFetchedStoriesAndEpics({ stories, epics });

      const epicGroupMap: Record<string, EpicGroup> = {};

      stories.forEach((s) => {
        if (!epicGroupMap[s.epicId]) {
          epicGroupMap[s.epicId] = {
            epicId: s.epicId,
            epicTitle: s.epicTitle,
            stories: [],
          };
        }
        epicGroupMap[s.epicId].stories.push({
          storyId: s.storyId,
          epicId: s.epicId,
          storyTitle: s.storyTitle,
          description: s.description,
          priority: normalizePriority(s.priority) ?? "Medium",
          acceptanceCriteria: s.acceptanceCriteria
            ? [s.acceptanceCriteria]
            : [],
          status: s.status,
          alreadyExists: s.alreadyExists,
        });
      });

      setTableData(Object.values(epicGroupMap));
      setIsJiraImport(true);
      setHasJiraImported(true);
      onMarkPasteOrUpload?.(false);
      message.success(`Fetched ${stories.length} stories from Jira`);
      onFileUploaded();
    } catch (error) {
      if (error instanceof JiraNotConfiguredError) {
        modal.error({
          title: "Jira credentials not set up",
          content: error.message,
        });
        return;
      }
      message.error(
        error instanceof Error
          ? error.message
          : "Failed to import stories from Jira",
      );
    } finally {
      setJiraLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!selectedProject) {
      message.error("Select a project first.");
      return;
    }
    try {
      setRefreshLoading(true);

      if (!fetchedStoriesAndEpics) {
        message.error(
          "Please import stories from Jira first before refreshing.",
        );
        return;
      }
      // Fast preview check: short-circuit if nothing changed in Jira vs DB.
      // Avoids expensive full fetch & sanitization on no-op clicks.
      const result = await refreshFromJira(selectedProject, selectedStatuses);
      if (
        !result.changed_story_keys?.length &&
        !result.new_story_keys?.length
      ) {
        setRefreshResult(result);
        setFrontendNewStories([]);
        pendingRefreshRef.current = null;
        setRefreshModalOpen(true);
        return;
      }

      const { stories, epics } = await fetchAllFromJira(
        selectedProject,
        selectedStatuses,
      );

      const previousStoriesMap = new Map<
        string,
        {
          storyTitle: string;
          description: string;
          acceptanceCriteria?: string;
          epicId: string;
        }
      >();
      tableData.forEach((epic) => {
        epic.stories.forEach((s) => {
          const acString = Array.isArray(s.acceptanceCriteria)
            ? s.acceptanceCriteria.join("\n")
            : s.acceptanceCriteria ?? "";
          previousStoriesMap.set(s.storyId, {
            storyTitle: s.storyTitle,
            description: s.description,
            acceptanceCriteria: acString,
            epicId: s.epicId || epic.epicId,
          });
        });
      });

      const frontendNewStoryIds: string[] = [];
      const frontendChangedStoryKeys: string[] = [];

      stories.forEach((s) => {
        const prev = previousStoriesMap.get(s.storyId);
        if (!prev) {
          frontendNewStoryIds.push(s.storyId);
        } else {
          const titleChanged =
            (s.storyTitle ?? "").trim() !== (prev.storyTitle ?? "").trim();
          const descChanged =
            (s.description ?? "").trim() !== (prev.description ?? "").trim();
          const acChanged =
            (s.acceptanceCriteria ?? "").trim() !==
            (prev.acceptanceCriteria ?? "").trim();
          const epicChanged =
            (s.epicId ?? "").trim() !== (prev.epicId ?? "").trim();

          if (titleChanged || descChanged || acChanged || epicChanged) {
            frontendChangedStoryKeys.push(s.storyId);
          }
        }
      });

      // The UI table represents the user's active working session. Diff against
      // tableData so unpersisted working-draft stories aren't re-flagged as new.
      const allChangedKeys = Array.from(new Set(frontendChangedStoryKeys));
      const allNewKeys = Array.from(new Set(frontendNewStoryIds));

      if (allChangedKeys.length === 0 && allNewKeys.length === 0) {
        message.info("All user stories are already up to date with Jira.");
        return;
      }

      setRefreshResult({
        success: true,
        changed_story_keys: allChangedKeys,
        new_story_keys: allNewKeys,
      });
      setFrontendNewStories(allNewKeys);

      const epicGroupMap: Record<string, EpicGroup> = {};
      stories.forEach((s) => {
        if (!epicGroupMap[s.epicId]) {
          epicGroupMap[s.epicId] = {
            epicId: s.epicId,
            epicTitle: s.epicTitle,
            stories: [],
          };
        }
        epicGroupMap[s.epicId].stories.push({
          storyId: s.storyId,
          epicId: s.epicId,
          storyTitle: s.storyTitle,
          description: s.description,
          priority: normalizePriority(s.priority) ?? "Medium",
          acceptanceCriteria: s.acceptanceCriteria
            ? [s.acceptanceCriteria]
            : [],
          status: s.status,
          alreadyExists: s.alreadyExists,
        });
      });

      // Held back until "Apply Changes": the refresh only reports what differs,
      // so the table keeps showing the imported stories until the user accepts.
      pendingRefreshRef.current = {
        stories,
        epics,
        tableData: Object.values(epicGroupMap),
        changedStoryKeys: allChangedKeys,
        newStoryIds: allNewKeys,
      };
      setRefreshModalOpen(true);
    } catch (error) {
      if (error instanceof JiraNotConfiguredError) {
        modal.error({
          title: "Jira credentials not set up",
          content: error.message,
        });
        return;
      }
      message.error(error instanceof Error ? error.message : "Refresh failed");
    } finally {
      setRefreshLoading(false);
    }
  };

  const handleStatusChange = (values: string[]) => {
    setSelectedStatuses(values);
    if (hasJiraImported) {
      setHasJiraImported(false);
      setFetchedStoriesAndEpics(null);
      setFrontendNewStories([]);
      onRefreshChanged?.([]);
      onNewStoriesDetected?.([]);
      setTableData([]);
      onFileRemoved();
    }
  };

  const uploadProps: UploadProps = {
    name: "file",
    multiple: false,
    pastable: true,
    accept: ".xlsx,.csv,text/csv",
    showUploadList: { showRemoveIcon: true },
    fileList,
    onChange: (info) => {
      const sanitizedList = info.fileList.map((file) => ({
        uid: file.uid,
        name: file.name ?? "",
        status: file.status ?? "done",
        size: file.size,
        type: file.type,
      }));
      dispatch(setUploadedFiles(sanitizedList));
    },
    beforeUpload: (file) => {
      const isXlsx =
        file.type ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const isCSV =
        file.type === "text/csv" ||
        file.type === "application/csv" ||
        file.name.toLowerCase().endsWith(".csv");

      if (!isXlsx && !isCSV) {
        message.error("Only .xlsx and .csv files are supported.");
        return Upload.LIST_IGNORE;
      }

      setIsJiraImport(false);
      setHasJiraImported(false);
      onMarkPasteOrUpload?.(true);
      onImportLoadingChange?.(true);
      onRefreshChanged?.([]);
      onNewStoriesDetected?.([]);
      void readData(file).finally(() => onImportLoadingChange?.(false));
      onFileUploaded();
      return false;
    },
    onRemove: () => {
      dispatch(setUploadedFiles([]));
      setTableData([]);
      setHasJiraImported(false);
      onMarkPasteOrUpload?.(false);
      onRefreshChanged?.([]);
      onNewStoriesDetected?.([]);
      onFileRemoved();
    },
  };

  const resetForProject = (value: string) => {
    dispatch(setProjectId(value));
    dispatch(clearTestGenerationState());
    setTableData([]);
    setIsJiraImport(false);
    setHasJiraImported(false);
    setActiveTab("jira");
    onMarkPasteOrUpload?.(false);
    onFileRemoved();
    setFrontendNewStories([]);
    onRefreshChanged?.([]);
    onNewStoriesDetected?.([]);
    setSelectedStatuses([]);
    setStatusesLoading(true);
    dispatch(setUploadedFiles([]));
    setJiraLoading(false);
    setRefreshLoading(false);
  };

  // New stories count too: applying is what puts them in the table.
  const hasRefreshChanges =
    (refreshResult?.changed_story_keys?.length ?? 0) > 0 ||
    frontendNewStories.length > 0;

  const tabs: { key: ImportTab; label: string; icon: React.ReactNode }[] = [
    { key: "jira", label: "Jira", icon: <JiraSVG /> },
    { key: "excel", label: "Excel / CSV", icon: <ExcelSVG /> },
    // { key: "ado", label: "Azure DevOps", icon: <AdoSVG /> },
  ];

  return (
    <div className="user-story-container">
      <div className="user-story-header">
        <div className="user-story-left">
          <div className="tg-section-num">1</div>
          <div>
            <h2 className="user-story-title">Import User Stories</h2>
            <p className="user-story-subtitle">
              Connect a source and import stories to begin
            </p>
          </div>
        </div>

        <ConfigProvider
          theme={{
            token: {
              colorPrimary: "#1f3333",
              controlOutline: "rgba(31, 51, 51, 0.1)",
              controlItemBgActive: "#eef2f2",
            },
          }}
        >
          <Select
            id="tg-project-select"
            className="ra-select project-select"
            placeholder={
              projectsLoading
                ? "Loading projects…"
                : projectOptions.length
                ? "Select a project"
                : "No projects found"
            }
            value={selectedProject ?? undefined}
            onChange={resetForProject}
            size="middle"
            options={projectOptions}
            showSearch={{ optionFilterProp: "label" }}
            suffixIcon={null}
            loading={projectsLoading}
            disabled={projectsLoading}
            notFoundContent={
              projectsLoading ? <Spin size="small" /> : "No projects found"
            }
          />
        </ConfigProvider>
      </div>

      <div className="usi-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`usi-tab${activeTab === tab.key ? " active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <span className="usi-tab-icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* All tabs always rendered - CSS grid stacks them so container height stays fixed */}
      <div className="usi-tab-body">
        <div
          className={`usi-slot-jira${
            activeTab !== "jira" ? " usi-panel-hidden" : ""
          }`}
        >
          <JiraTabPanel
            active={activeTab === "jira"}
            hasJiraImported={hasJiraImported}
            isFileUploaded={isFileUploaded}
            isJiraImport={isJiraImport}
            selectedProject={!selectedProject}
            jiraLoading={jiraLoading}
            refreshLoading={refreshLoading}
            statusOptions={jiraStatuses}
            selectedStatuses={selectedStatuses}
            statusesLoading={statusesLoading && !!selectedProject}
            onStatusChange={handleStatusChange}
            onImport={handleJiraImport}
            onRefresh={handleRefresh}
          />
        </div>

        <div className={activeTab !== "excel" ? "usi-panel-hidden" : ""}>
          <ExcelTabPanel
            uploadProps={uploadProps}
            fileList={fileList}
            isFileUploaded={isFileUploaded}
            isJiraImport={isJiraImport}
            selectedProject={!selectedProject}
          />
        </div>

        {/* <div
          className={`usi-slot-ado${
            activeTab !== "ado" ? " usi-panel-hidden" : ""
          }`}
        >
          <AdoTabPanel />
        </div> */}
      </div>

      <Modal
        title="Refresh from Jira - Changes Detected"
        open={refreshModalOpen}
        confirmLoading={applyLoading}
        closable={!applyLoading}
        mask={{ closable: !applyLoading }}
        onOk={async () => {
          const pending = pendingRefreshRef.current;
          // Nothing changed: leave the table (and any in-progress edits) alone.
          const hasChanges =
            !!pending &&
            (pending.changedStoryKeys.length > 0 ||
              pending.newStoryIds.length > 0);
          if (pending && hasChanges && selectedProject) {
            setApplyLoading(true);
            try {
              // Suppress the window-focus enrichment so it can't overwrite the
              // fresh data we're about to set.
              refreshJustAppliedRef.current = true;

              let syncFailed = false;

              // Persist updated stories to the database directly using the fresh epics payload.
              if (pending.changedStoryKeys.length) {
                try {
                  await applyRefreshChanges(
                    selectedProject,
                    selectedStatuses,
                    pending.epics,
                  );
                } catch (error) {
                  syncFailed = true;
                  if (error instanceof JiraNotConfiguredError) {
                    modal.error({
                      title: "Jira credentials not set up",
                      content: error.message,
                    });
                  } else {
                    message.warning(
                      error instanceof Error
                        ? `Table updated. DB sync failed: ${error.message}`
                        : "Table updated, but could not persist changes to the database.",
                    );
                  }
                }
              }

              // Always update the UI with the fresh Jira data first — the table
              // must reflect the latest stories regardless of whether the DB
              // persist succeeds or fails.
              setFetchedStoriesAndEpics({
                stories: pending.stories,
                epics: pending.epics,
              });
              setTableData(pending.tableData);
              onRefreshChanged?.(pending.changedStoryKeys);
              onNewStoriesDetected?.(pending.newStoryIds);
              pendingRefreshRef.current = null;
              setRefreshModalOpen(false);

              if (!syncFailed) {
                message.success("Refresh successful");
              }
            } finally {
              setApplyLoading(false);
              // Allow the enrichment effect to resume after the UI has settled.
              setTimeout(() => {
                refreshJustAppliedRef.current = false;
              }, 1500);
            }
          } else {
            setRefreshModalOpen(false);
          }
        }}
        onCancel={() => {
          if (applyLoading) return;
          // Discard the refresh: the table keeps the stories it already had.
          pendingRefreshRef.current = null;
          setFrontendNewStories([]);
          setRefreshModalOpen(false);
        }}
        okText={hasRefreshChanges ? "OK - Apply Changes" : "OK"}
        cancelButtonProps={{
          disabled: applyLoading,
          style: {
            display: hasRefreshChanges ? "inline-block" : "none",
          },
        }}
      >
        {refreshResult && (
          <div style={{ fontSize: 14, lineHeight: "2" }}>
            {refreshResult.changed_story_keys.length === 0 &&
            frontendNewStories.length === 0 ? (
              <p>✅ No changes detected.</p>
            ) : (
              <>
                {refreshResult.changed_story_keys.length > 0 && (
                  <>
                    <p>
                      🔄{" "}
                      <strong>
                        {refreshResult.changed_story_keys.length} existing
                        stories changed
                      </strong>
                    </p>
                    <ul>
                      {refreshResult.changed_story_keys.map((key) => (
                        <li key={key}>
                          <code>{key}</code>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {frontendNewStories.length > 0 && (
                  <>
                    <p>
                      🆕{" "}
                      <strong>
                        {frontendNewStories.length} new user stories added
                      </strong>{" "}
                      (not saved to DB):
                    </p>
                    <ul>
                      {frontendNewStories.map((key) => (
                        <li key={key}>
                          <code>{key}</code>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
