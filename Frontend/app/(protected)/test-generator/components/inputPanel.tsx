"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Checkbox, Tooltip, App, Pagination, Skeleton } from "antd";
import type { JiraEpic } from "@/types/jira";
import { saveStoriesToDb, saveStoryEditLog } from "@/services/databaseService";
import type { StoryEditRecord } from "@/services/databaseService";
import type { ApprovalEpic } from "@/types/storyApproval";
import {
  BrowseDocumentsModal,
  useContextDocumentUpload,
  type BrowsableDoc,
} from "@/components/ContextDocumentsPanel";
import {
  CheckCircleFilled,
  FileTextOutlined,
  ApartmentOutlined,
  DownOutlined,
  RightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  UserOutlined,
  EditOutlined,
  DeleteOutlined,
  LoadingOutlined,
  FolderOpenOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import UserStoryInput from "./UserStoryInput";
import SendForApprovalModal from "./SendForApprovalModal";
import InlineStoryEditor from "./InlineStoryEditor";
import type { EditDraft } from "./InlineStoryEditor";
import MissingFieldsBadge from "./MissingFieldsBadge";
import {
  ContextDocumentRequest,
  Priority,
  StoryStatus,
  EpicGroup,
  UserStoryRow,
  GenerationSettings,
  TestGeneratorRequest,
  WorkflowStep,
} from "@/types/testGenerator";
import {
  buildTestGeneratorRequest,
  computeStoryDiff,
  getMissingFields,
} from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import {
  StoryChange,
  getStoryDisplayStatus,
} from "@/utils/testcaseGenerator/testcaseGeneratorHelpers";
import "../assets/css/UserStoryInput.css";
import AITable from "@/components/AITable";
import type { ColumnsType } from "antd/es/table";
import GenerationSettingsPanel from "./GenerationSettings";
import { ACCEPTED_FILE_TYPES, PERMISSIONS } from "@/constants";
import { usePermissions } from "@/hooks/usePermissions";

import { useAppDispatch, useAppSelector } from "@/store/store";
import {
  setContextDocuments,
  setImpactPrompt,
  setTableData,
  setIsJiraImport,
  setHasInputFromPasteOrUpload,
  setIsFileUploaded,
  setHasSavedToDb,
  updateStoryInTableData,
  markStoriesInReview,
  clearTestGenerationState,
  setSelectedStoryIds as setSelectedStoryIdsAction,
} from "@/store/slices/testGenerationSlice";
import { BackendProject } from "@/types/project";
import type { UseActionCooldownResult } from "@/hooks/useActionCooldown";
import CooldownNotice from "@/components/CooldownNotice";

type TableRow =
  | {
      id: string;
      storyId: string;
      isEpic: true;
      epicId: string;
      epicTitle: string;
      storyCount: number;
      isCollapsed: boolean;
    }
  | (UserStoryRow & {
      isEpic: false;
      epicId: string;
      epicTitle: string;
    });

const EPICS_PER_PAGE = 3;

function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={`tg-priority-badge ${priority}`}>{priority}</span>;
}

function StatusBadge({ status }: { status: StoryStatus | string }) {
  const isPending = status === "Pending Review";
  const isApproved = status === "Approved" || status === "Already Approved";
  const isInReview = status === "In Review";

  return (
    <span
      className={`tg-status-badge ${
        isInReview
          ? "InReview"
          : isPending
          ? "Pending"
          : isApproved
          ? "Approved"
          : "Rejected"
      }`}
    >
      {isApproved && <CheckCircleOutlined style={{ fontSize: 10 }} />}
      {isInReview && <ClockCircleOutlined style={{ fontSize: 10 }} />}
      {status}
    </span>
  );
}

function ModifiedBadge({ count }: { count: number }) {
  return (
    <span className="tg-modified-badge">
      <EditOutlined style={{ fontSize: 9 }} />
      {count} {count === 1 ? "field" : "fields"} edited
    </span>
  );
}

function ContextDocumentsSection({
  docs,
  onFilesSelected,
  onRemove,
  uploadingFileNames,
  selectedProject,
  onAddExistingDocs,
}: {
  docs: ContextDocumentRequest[];
  onFilesSelected: (files: FileList | null) => void;
  onRemove: (index: number) => void;
  uploadingFileNames: Set<string>;
  selectedProject: BackendProject | null;
  onAddExistingDocs: (docs: BrowsableDoc[]) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [browseOpen, setBrowseOpen] = useState(false);

  const handleAddClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilesSelected(e.target.files);

    // Reset so the same file can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="tg-section-card">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FILE_TYPES.join(",")}
        multiple
        style={{ display: "none" }}
        onChange={handleFileSelected}
      />

      <div className="tg-section-header">
        <div className="tg-section-num orange">3</div>
        <div style={{ flex: 1 }}>
          <div className="tg-section-title">
            Attach Sanitized Context Documents
          </div>
          <div className="tg-section-subtitle">
            Upload PDF, DOCX, XLSX, CSV or TXT files that help the AI generate
            better test cases
          </div>
        </div>
      </div>
      <div className="tg-section-body">
        <div className="tg-context-doc-list">
          {docs.map((doc, index) => {
            const isUploading = doc.fileName
              ? uploadingFileNames.has(doc.fileName)
              : false;

            return (
              <div
                key={doc.documentId || index}
                className="tg-context-doc-item"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  background: "#f5f7fa",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  opacity: isUploading ? 0.8 : 1,
                  transition: "opacity 0.2s ease",
                }}
              >
                {isUploading ? (
                  <LoadingOutlined
                    style={{ fontSize: 15, color: "#2563eb", flexShrink: 0 }}
                  />
                ) : (
                  <FileTextOutlined
                    style={{ fontSize: 15, color: "#6b7280", flexShrink: 0 }}
                  />
                )}
                <span
                  style={{
                    flex: 1,
                    fontSize: 13,
                    color: "#1f2937",
                    fontWeight: 500,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {doc.title}
                  {isUploading && (
                    <span style={{ color: "#9ca3af", fontWeight: 400 }}>
                      {" "}
                      - uploading…
                    </span>
                  )}
                </span>
                <button
                  className="tg-context-doc-remove"
                  onClick={() => onRemove(index)}
                  type="button"
                  aria-label={`Remove ${doc.title}`}
                  disabled={isUploading}
                  style={{ opacity: isUploading ? 0.4 : 1 }}
                >
                  <DeleteOutlined />
                </button>
              </div>
            );
          })}

          <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
            <button
              type="button"
              onClick={handleAddClick}
              style={{
                display: "flex",
                alignItems: "center",
                flex: 1,
                padding: "9px 14px",
                background: "none",
                border: "1.5px dashed #d1d5db",
                borderRadius: 8,
                fontSize: 13,
                color: "#6b7280",
                cursor: "pointer",
                transition: "border-color 0.15s, color 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "#1f3333";
                e.currentTarget.style.color = "#1f3333";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "#d1d5db";
                e.currentTarget.style.color = "#6b7280";
              }}
            >
              <FileTextOutlined style={{ marginRight: 6 }} />
              {docs.length === 0 ? "Add a document" : "Add another document"}
            </button>

            <button
              type="button"
              onClick={() => setBrowseOpen(true)}
              disabled={!selectedProject}
              style={{
                display: "flex",
                alignItems: "center",
                flex: 1,
                padding: "9px 14px",
                background: "none",
                border: "1.5px dashed #d1d5db",
                borderRadius: 8,
                fontSize: 13,
                color: selectedProject ? "#6b7280" : "#c1c5cb",
                cursor: selectedProject ? "pointer" : "not-allowed",
                transition: "border-color 0.15s, color 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!selectedProject) return;
                e.currentTarget.style.borderColor = "#1f3333";
                e.currentTarget.style.color = "#1f3333";
              }}
              onMouseLeave={(e) => {
                if (!selectedProject) return;
                e.currentTarget.style.borderColor = "#d1d5db";
                e.currentTarget.style.color = "#6b7280";
              }}
            >
              <FolderOpenOutlined style={{ marginRight: 6 }} />
              Add from Client / Programme / Project
            </button>
          </div>

          <BrowseDocumentsModal
            open={browseOpen}
            onClose={() => setBrowseOpen(false)}
            selectedProject={selectedProject}
            existingDocumentIds={
              new Set(docs.map((d) => d.documentId).filter(Boolean) as string[])
            }
            onAdd={(selected) => {
              if (selected.length === 0) return;
              onAddExistingDocs(selected);
            }}
          />
        </div>
      </div>
    </div>
  );
}

function ImpactPromptSection({
  open,
  impactPromptText,
  onToggle,
  onChange,
}: {
  open: boolean;
  impactPromptText: string;
  onToggle: () => void;
  onChange: (value: string) => void;
}) {
  return (
    <div className="tg-section-card">
      <div
        className="tg-section-header"
        style={{
          cursor: "pointer",
          borderBottom: open ? "1px solid #f3f4f6" : "none",
        }}
        onClick={onToggle}
      >
        <div className="tg-section-num purple">4</div>
        <div style={{ flex: 1 }}>
          <div className="tg-section-title">Impact Prompt</div>
          <div className="tg-section-subtitle">
            Add optional context or constraints for the LLM (click to expand)
          </div>
        </div>
        <DownOutlined
          style={{
            fontSize: 12,
            color: "#9ca3af",
            marginLeft: 8,
            transition: "transform 0.2s",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
      </div>

      {open && (
        <div className="tg-section-body" style={{ paddingTop: 10 }}>
          <textarea
            className="tg-impact-textarea"
            placeholder="Enter text"
            value={impactPromptText}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: 8,
            }}
          >
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {impactPromptText.length} characters
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function ApprovalBanner({
  selectedCount,
  totalCount,
  selectedApprovedCount,
  onGenerate,
  onRegenerate,
  isGenerated,
  isProcessing,
  canGenerate,
  cooldown,
  disabledReason,
}: {
  selectedCount: number;
  totalCount: number;
  selectedApprovedCount: number;
  onGenerate: () => void;
  onRegenerate: () => void;
  isGenerated: boolean;
  isProcessing: boolean;
  canGenerate: boolean;
  cooldown: UseActionCooldownResult;
  disabledReason?: string;
}) {
  const isDisabled = isProcessing || !canGenerate || cooldown.isCoolingDown;

  return (
    <div className="tg-approval-banner">
      <div className="tg-approval-banner-left">
        <CheckCircleFilled className="tg-approval-banner-icon" />
        <div className="tg-approval-banner-text">
          <strong>
            {selectedCount === totalCount
              ? "Stories Approved"
              : `${selectedCount} of ${totalCount} stories approved`}
            {selectedApprovedCount > 0 &&
              ` (${selectedApprovedCount} selected)`}
          </strong>
          <span className="tg-approval-banner-hint">
            {disabledReason
              ? disabledReason
              : isGenerated
              ? "Test cases generated. You can regenerate with updated context."
              : "You can now attach context and generate test cases."}
          </span>
          {cooldown.isCoolingDown && (
            <CooldownNotice
              actionLabel="Test Generation"
              formattedTime={cooldown.formatted}
            />
          )}
        </div>
      </div>

      <Tooltip
        title={
          isDisabled && !cooldown.isCoolingDown ? disabledReason : undefined
        }
      >
        <span>
          {isGenerated ? (
            <button
              className="tg-btn tg-btn-success"
              onClick={onRegenerate}
              disabled={isDisabled}
            >
              <SyncOutlined />
              Regenerate
            </button>
          ) : (
            <button
              className="tg-btn tg-btn-primary"
              onClick={onGenerate}
              disabled={isDisabled}
            >
              <ThunderboltOutlined />
              Generate Test Cases
            </button>
          )}
        </span>
      </Tooltip>
    </div>
  );
}

interface InputPanelProps {
  workflowStep: WorkflowStep;
  generationSettings: GenerationSettings;
  onGenerationSettingsChange: (settings: GenerationSettings) => void;
  onStoriesUploaded: () => void;
  onGenerate: (request: TestGeneratorRequest) => void;
  onRegenerate: (request: TestGeneratorRequest) => void;
  isProcessing: boolean;
  cooldown: UseActionCooldownResult;
}

export default function InputPanel({
  workflowStep,
  generationSettings,
  onGenerationSettingsChange,
  onStoriesUploaded,
  onGenerate,
  onRegenerate,
  isProcessing,
  cooldown,
}: InputPanelProps) {
  const { message } = App.useApp();
  const dispatch = useAppDispatch();
  // Submitting for approval needs STORY_REQUEST_APPROVAL (enforced by the backend);
  // hide the button for anyone without it instead of showing a control that 403s.
  const { hasPermission } = usePermissions();
  const canRequestApproval = hasPermission(PERMISSIONS.STORY_REQUEST_APPROVAL);
  const {
    contextDocuments,
    impactPrompt,
    tableData,
    originalTableData,
    isJiraImport,
    isFileUploaded,
    hasSavedToDb,
    selectedStoryIds: rawSelectedStoryIds = [],
  } = useAppSelector((state) => state.testGeneration.inputState);

  const [epicPage, setEpicPage] = useState(1);
  const [importLoading, setImportLoading] = useState(false);

  const selectedStoryIds = useMemo(
    () => new Set(rawSelectedStoryIds),
    [rawSelectedStoryIds],
  );

  const setSelectedStoryIds = useCallback(
    (next: Set<string> | string[]) => {
      const arr = Array.isArray(next) ? next : Array.from(next);
      dispatch(setSelectedStoryIdsAction(arr));
    },
    [dispatch],
  );
  const [impactPromptOpen, setImpactPromptOpen] = useState(false);

  // Stories already sent for approval and awaiting a decision — cannot be selected
  // for a fresh approval submission (the backend would reject the duplicate anyway).
  const inReviewStoryIds = useMemo(
    () =>
      new Set(
        tableData
          .flatMap((group) => group.stories)
          .filter(
            (story) =>
              story.status?.trim().toLowerCase() === "pending_approval",
          )
          .map((story) => story.storyId),
      ),
    [tableData],
  );

  const originalStoryMap = useMemo(() => {
    const map = new Map<string, UserStoryRow>();
    originalTableData.forEach((g) =>
      g.stories.forEach((s) => map.set(s.storyId, s)),
    );
    return map;
  }, [originalTableData]);

  const storyChanges = useMemo(() => {
    const changes = new Map<string, StoryChange[]>();
    tableData.forEach((g) => {
      g.stories.forEach((s) => {
        const orig = originalStoryMap.get(s.storyId);
        if (!orig) return;
        const diff = computeStoryDiff(orig, s);
        if (diff.length > 0) changes.set(s.storyId, diff);
      });
    });
    return changes;
  }, [tableData, originalStoryMap]);

  const [collapsedEpics, setCollapsedEpics] = useState<Set<string>>(new Set());
  const toggleEpic = (epicId: string) => {
    setCollapsedEpics((prev) => {
      const next = new Set(prev);
      if (next.has(epicId)) next.delete(epicId);
      else next.add(epicId);
      return next;
    });
  };
  const [changedStoryKeys, setChangedStoryKeys] = useState<Set<string>>(
    new Set(),
  );
  const [newStoryKeys, setNewStoryKeys] = useState<Set<string>>(new Set());
  const [selectedProject, setSelectedProject] = useState<BackendProject | null>(
    null,
  );
  const [editingStoryId, setEditingStoryId] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<EditDraft | null>(null);
  const [editingOriginal, setEditingOriginal] = useState<EditDraft | null>(
    null,
  );
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);

  const previousTableDataLength = useRef(tableData.length);
  const previousEpicIdsRef = useRef(tableData.map((g) => g.epicId).join("\0"));
  useEffect(() => {
    const currentEpicIds = tableData.map((g) => g.epicId).join("\0");
    const isNewImport =
      previousTableDataLength.current === 0 && tableData.length > 0;
    // Catches re-imports at the same epic count (same-length swap)
    const isReplacement =
      tableData.length > 0 && currentEpicIds !== previousEpicIdsRef.current;

    if (isNewImport || isReplacement) {
      setSelectedStoryIds(new Set());
      setEpicPage(1);
      setCollapsedEpics(new Set());
    }

    previousTableDataLength.current = tableData.length;
    previousEpicIdsRef.current = currentEpicIds;
  }, [tableData, setSelectedStoryIds]);

  const {
    uploadingFileNames,
    handleFilesSelected: handleContextFilesSelected,
    handleRemoveDoc,
    handleAddExistingDocs,
  } = useContextDocumentUpload({
    selectedProject,
    contextDocs: contextDocuments,
    setContextDocs: (docs) => dispatch(setContextDocuments(docs)),
    autoFetch: true,
    onError: (msg) => message.error(msg),
    onNotice: (msg, kind) =>
      kind === "info" ? message.info(msg) : message.success(msg),
  });
  const [sendForApprovalOpen, setSendForApprovalOpen] = useState(false);

  const showStories =
    workflowStep === "review" ||
    workflowStep === "approved" ||
    workflowStep === "generated";
  const isGenerated = workflowStep === "generated";

  const allStories = useMemo(
    () => tableData.flatMap((g: EpicGroup) => g.stories || []),
    [tableData],
  );
  const storiesWithMissingFields = useMemo(
    () => allStories.filter((s) => getMissingFields(s).length > 0),
    [allStories],
  );
  const missingFieldsCount = storiesWithMissingFields.length;

  const effectiveApprovedStoryIds = useMemo(
    () =>
      new Set<string>(
        allStories
          .filter((story) => {
            const normalizedStatus = story.status?.trim().toLowerCase();
            return (
              normalizedStatus === "approved" ||
              normalizedStatus === "already approved"
            );
          })
          .map((story) => story.storyId),
      ),
    [allStories],
  );
  const hasApprovedStories = effectiveApprovedStoryIds.size > 0;
  const isApproved =
    workflowStep === "approved" ||
    workflowStep === "generated" ||
    hasApprovedStories;
  const state = isApproved ? "approved" : "pending";
  // Full content of the currently-selected stories, grouped by epic, for the
  // Send-for-Approval submit — the backend upserts these into user_stories in the
  // same transaction as the approval requests. Approved stories are eligible: an
  // edited story can go back for re-review. In-review ones aren't — the backend
  // dedupes a second pending request for the same (story, reviewer) pair.
  const approvalEpics = useMemo<ApprovalEpic[]>(
    () =>
      tableData
        .map((group) => ({
          epicId: group.epicId,
          epicTitle: group.epicTitle,
          user_stories: group.stories
            .filter(
              (story) =>
                selectedStoryIds.has(story.storyId) &&
                !inReviewStoryIds.has(story.storyId),
            )
            .map((story) => ({
              storyId: story.storyId,
              storyTitle: story.storyTitle,
              description: story.description,
              acceptanceCriteria: Array.isArray(story.acceptanceCriteria)
                ? story.acceptanceCriteria.join(" | ")
                : story.acceptanceCriteria || "",
              issue_type: "story",
              priority: story.priority ?? null,
            })),
        }))
        .filter((epic) => epic.user_stories.length > 0),
    [tableData, selectedStoryIds, inReviewStoryIds],
  );

  const selectedStories = useMemo(
    () => allStories.filter((s) => selectedStoryIds.has(s.storyId)),
    [allStories, selectedStoryIds],
  );

  const [selectedApprovedStories, selectedUnapprovedStories] = useMemo(() => {
    const approved: UserStoryRow[] = [];
    const unapproved: UserStoryRow[] = [];
    for (const s of selectedStories) {
      (effectiveApprovedStoryIds.has(s.storyId) ? approved : unapproved).push(
        s,
      );
    }
    return [approved, unapproved] as const;
  }, [selectedStories, effectiveApprovedStoryIds]);

  const selectableStoryIds = useMemo(
    () =>
      allStories
        .filter((s) => !inReviewStoryIds.has(s.storyId))
        .map((s) => s.storyId),
    [allStories, inReviewStoryIds],
  );

  const showBanner =
    workflowStep === "approved" ||
    workflowStep === "generated" ||
    hasApprovedStories;
  const showContext = showBanner;

  const canGenerate =
    selectedApprovedStories.length > 0 &&
    selectedUnapprovedStories.length === 0 &&
    contextDocuments.length > 0;

  const generateHelpText = useMemo(() => {
    if (selectedStoryIds.size === 0) {
      return "Select at least one approved user story to generate test cases.";
    }
    if (selectedApprovedStories.length === 0) {
      return "None of the selected stories are approved yet.";
    }
    if (selectedUnapprovedStories.length > 0) {
      return `${selectedUnapprovedStories.length} of the selected stories are not approved yet.`;
    }
    if (contextDocuments.length === 0) {
      return "Attach at least one context document.";
    }
    return "";
  }, [
    selectedStoryIds.size,
    selectedApprovedStories.length,
    selectedUnapprovedStories.length,
    contextDocuments.length,
  ]);

  const handleEditInline = (e: React.MouseEvent, story: UserStoryRow) => {
    e.stopPropagation();
    // A story awaiting a reviewer decision is locked: editing it would silently
    // change what the reviewer is reviewing. It unlocks once the decision lands.
    if (inReviewStoryIds.has(story.storyId)) return;
    const original: EditDraft = {
      storyTitle: story.storyTitle ?? "",
      description: story.description ?? "",
      acceptanceCriteria: (story.acceptanceCriteria ?? []).join("\n"),
    };
    setEditingOriginal(original);
    setEditingDraft({ ...original });
    setEditingStoryId(story.storyId);
    setExpandedRowKeys((prev) =>
      prev.includes(story.storyId) ? prev : [...prev, story.storyId],
    );
  };

  const handleCancelEdit = () => {
    const sid = editingStoryId;
    setEditingStoryId(null);
    setEditingDraft(null);
    setEditingOriginal(null);
    setExpandedRowKeys((prev) => prev.filter((k) => k !== sid));
  };

  const handleSaveEdit = () => {
    if (!editingDraft || !editingStoryId) return;

    const newTitle = editingDraft.storyTitle.trim();
    const newDesc = editingDraft.description.trim();
    const newAC = editingDraft.acceptanceCriteria
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const stillMissing = getMissingFields({
      storyTitle: newTitle,
      description: newDesc,
      acceptanceCriteria: newAC,
    });

    if (stillMissing.length > 0) {
      message.error(`Please fill in: ${stillMissing.join(", ")}`);
      return;
    }

    const storyId = editingStoryId;

    dispatch(
      updateStoryInTableData({
        storyId,
        storyTitle: newTitle,
        description: newDesc,
        acceptanceCriteria: newAC,
      }),
    );

    message.success("Story updated");
    setEditingStoryId(null);
    setEditingDraft(null);
    setEditingOriginal(null);
    setExpandedRowKeys((prev) => prev.filter((k) => k !== storyId));
  };

  const handleRowExpand = (expanded: boolean, record: TableRow) => {
    if (record.isEpic) return;
    if (expanded) {
      setExpandedRowKeys((prev) =>
        prev.includes(record.storyId) ? prev : [...prev, record.storyId],
      );
    } else {
      setExpandedRowKeys((prev) => prev.filter((k) => k !== record.storyId));
      if (editingStoryId === record.storyId) {
        setEditingStoryId(null);
        setEditingDraft(null);
        setEditingOriginal(null);
      }
    }
  };

  const handleFileUpload = () => {
    dispatch(setIsFileUploaded(true));
    dispatch(setHasInputFromPasteOrUpload(true));
    onStoriesUploaded();
  };

  const submitGeneration = async (isRegeneration = false) => {
    if (isProcessing || cooldown.isCoolingDown) {
      return;
    }

    if (selectedStoryIds.size === 0) {
      message.error(
        "Select at least one approved user story to generate test cases.",
      );
      return;
    }

    if (selectedApprovedStories.length === 0) {
      message.error("None of the selected stories are approved yet.");
      return;
    }

    if (selectedUnapprovedStories.length > 0) {
      message.error(
        `${selectedUnapprovedStories.length} of the selected stories are not approved yet. All selected stories must be approved first.`,
      );
      return;
    }

    if (contextDocuments.length === 0) {
      message.error("Attach at least one context document.");
      return;
    }

    const selectedApprovedIds = new Set(
      selectedApprovedStories.map((s) => s.storyId),
    );

    try {
      // Phase 1: persist stories to DB first so the edit log FK is satisfied
      if (tableData.length > 0) {
        const payload = tableData
          .map((group) => ({
            epicId: group.epicId,
            epicTitle: group.epicTitle,
            user_stories: group.stories
              .filter((story) => selectedApprovedIds.has(story.storyId))
              .map((story) => ({
                storyId: story.storyId,
                storyTitle: story.storyTitle,
                description: story.description,
                acceptanceCriteria: Array.isArray(story.acceptanceCriteria)
                  ? story.acceptanceCriteria.join(" | ")
                  : story.acceptanceCriteria || "",
                issue_type: "story",
                priority: story.priority ?? null,
              })),
          }))
          .filter((epic) => epic.user_stories.length > 0);

        if (!selectedProject) {
          message.error("Select a project first.");
          return;
        }

        try {
          const result = await saveStoriesToDb(
            payload as unknown as JiraEpic[],
            selectedProject.id,
          );

          dispatch(setHasSavedToDb(true));

          const insertedCount = result.inserted?.length || 0;
          const skippedCount = result.skipped?.length || 0;
          const insertedIds = result.inserted ?? [];
          const skippedIds = result.skipped ?? [];

          if (insertedCount > 0 && skippedCount > 0) {
            message.success(
              [
                `Saved (${insertedIds.length}): ${
                  insertedIds.join(", ") || "None"
                }`,
                `Skipped (${skippedIds.length}): ${
                  skippedIds.join(", ") || "None"
                }`,
              ].join("\n"),
              10,
            );
          } else if (insertedCount > 0) {
            message.success("All approved user stories added to DB.", 5);
          } else if (skippedCount > 0) {
            message.info(
              `${skippedCount} approved user stories already exist in DB.`,
              5,
            );
          }
        } catch (saveError) {
          console.error("DB save failed:", saveError);
          message.warning("DB save failed, continuing with test generation.");
        }
      }

      // Phase 2: save edit log after stories are in DB
      if (storyChanges.size > 0) {
        const editLog: StoryEditRecord[] = [];
        const editedAt = new Date().toISOString();
        tableData.forEach((group) => {
          group.stories.forEach((story) => {
            if (!selectedApprovedIds.has(story.storyId)) return;
            const changes = storyChanges.get(story.storyId);
            if (changes && changes.length > 0) {
              editLog.push({
                storyId: story.storyId,
                epicId: group.epicId,
                changes,
                editedAt,
              });
            }
          });
        });
        try {
          await saveStoryEditLog(editLog);
        } catch (err) {
          console.error(
            "Story edit log could not be saved after retries:",
            err,
          );
          message.error(
            "Could not save the story edit log after multiple attempts - generation blocked to preserve audit trail. Please try again.",
          );
          return;
        }
      }

      const request = buildTestGeneratorRequest({
        settings: generationSettings,
        epics: tableData,
        selectedStoryIds: selectedApprovedIds,
        contextDocuments,
        impactPrompt,
      });
      if (isRegeneration) {
        onRegenerate(request);
        return;
      }

      onGenerate(request);
    } catch (error) {
      message.error(
        error instanceof Error
          ? error.message
          : "Unable to build generation request.",
      );
    }
  };

  const columns: ColumnsType<TableRow> = [
    {
      title: "Story ID",
      dataIndex: "storyId",
      key: "id",
      width: "8%",
      ellipsis: true,
      render: (_: string, record: TableRow) => {
        if (record.isEpic) {
          return (
            <div
              className="tg-epic-group-label"
              onClick={(e) => {
                e.stopPropagation();
                toggleEpic(record.epicId);
              }}
            >
              <RightOutlined
                className={`tg-epic-chevron${
                  record.isCollapsed ? "" : " expanded"
                }`}
              />
              <ApartmentOutlined style={{ fontSize: 12 }} />
              {record.epicId} - {record.epicTitle}
              <span className="tg-epic-story-count">
                {record.storyCount}{" "}
                {record.storyCount === 1 ? "story" : "stories"}
              </span>
            </div>
          );
        }

        return <span className="tg-story-id">{record.storyId}</span>;
      },

      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 9 : 1,
      }),
    },
    {
      title: "Title",
      dataIndex: "storyTitle",
      key: "title",
      width: "16%",
      ellipsis: true,
      render: (value: string, record: TableRow) =>
        !record.isEpic ? <span className="tg-story-title">{value}</span> : null,

      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
      }),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      width: "34%",
      ellipsis: { showTitle: true },
      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
        className: "col-description",
      }),
      render: (value: string, record: TableRow) =>
        !record.isEpic ? <span className="tg-cell-desc">{value}</span> : null,
    },
    {
      title: "Priority",
      dataIndex: "priority",
      key: "priority",
      align: "center",
      width: "10%",
      render: (priority: Priority, record: TableRow) =>
        !record.isEpic ? <PriorityBadge priority={priority} /> : null,

      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
      }),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      align: "center",
      width: "18%",
      render: (_: string, record: TableRow) => {
        if (record.isEpic) return null;

        const status = getStoryDisplayStatus({
          status: record.status,
          isApproved: effectiveApprovedStoryIds.has(record.storyId),
        });
        const missing = getMissingFields(record);
        const edited = storyChanges.get(record.storyId);

        return (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              alignItems: "center",
            }}
          >
            <StatusBadge status={status} />
            {missing.length > 0 && (
              <MissingFieldsBadge count={missing.length} />
            )}
            {edited && edited.length > 0 && (
              <ModifiedBadge count={edited.length} />
            )}
          </div>
        );
      },

      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
      }),
    },
    {
      title: "",
      key: "actions",
      width: "12%",
      render: (_: unknown, record: TableRow) => {
        if (record.isEpic) return null;
        const isEditing = editingStoryId === record.storyId;

        if (isEditing) {
          return <span className="tg-editing-indicator">Editing…</span>;
        }

        if (inReviewStoryIds.has(record.storyId)) {
          return (
            <span
              title="Awaiting reviewer approval — can’t be edited until a decision is made."
              style={{ whiteSpace: "nowrap", fontSize: 11, color: "#94a3b8" }}
            >
              Under review
            </span>
          );
        }

        return (
          <button
            className="tg-btn tg-btn-ghost tg-btn-sm"
            onClick={(e) => handleEditInline(e, record)}
            type="button"
            style={{ whiteSpace: "nowrap" }}
          >
            <EditOutlined style={{ fontSize: 11 }} />
            Edit inline
          </button>
        );
      },
      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
      }),
    },
    {
      title: "",
      dataIndex: "alreadyExists",
      key: "exists",
      align: "left",
      width: "5%",
      render: (_: unknown, record: TableRow) => {
        if (record.isEpic || !record.alreadyExists) return null;

        return (
          <Tooltip title="Already exists in database">
            <InfoCircleOutlined
              style={{ color: "#1890ff", fontSize: 16, cursor: "default" }}
            />
          </Tooltip>
        );
      },
      onCell: (record: TableRow) => ({
        colSpan: record.isEpic ? 0 : 1,
      }),
    },
  ];

  const pagedEpics = tableData.slice(
    (epicPage - 1) * EPICS_PER_PAGE,
    epicPage * EPICS_PER_PAGE,
  );

  const handleEpicPageChange = (page: number) => {
    if (editingStoryId) handleCancelEdit();
    setEpicPage(page);
  };

  const flattenedStories = pagedEpics.flatMap((group) => {
    const isCollapsed = collapsedEpics.has(group.epicId);
    const epicRow: TableRow = {
      id: `epic-${group.epicId}`,
      storyId: `epic-${group.epicId}`,
      isEpic: true,
      epicId: group.epicId,
      epicTitle: group.epicTitle,
      storyCount: group.stories.length,
      isCollapsed,
    };
    if (isCollapsed) return [epicRow];
    return [
      epicRow,
      ...group.stories.map((story) => ({
        ...story,
        isEpic: false as const,
        epicId: group.epicId,
        epicTitle: group.epicTitle,
      })),
    ];
  });

  return (
    <div className="tg-panel tg-panel-left">
      <div className="tg-panel-scroll" style={{ overflowY: "auto" }}>
        <div key="user-story-input-stable" style={{ flexShrink: 0 }}>
          <UserStoryInput
            isFileUploaded={isFileUploaded}
            hasSavedToDb={hasSavedToDb}
            isJiraImport={isJiraImport}
            setIsJiraImport={(value) => {
              dispatch(setIsJiraImport(value));
              if (!value) {
                dispatch(setHasInputFromPasteOrUpload(false));
              }
            }}
            onFileUploaded={handleFileUpload}
            onFileRemoved={() => {
              dispatch(clearTestGenerationState());
            }}
            onMarkPasteOrUpload={(value) => {
              dispatch(setHasInputFromPasteOrUpload(value));
            }}
            setTableData={(data) => dispatch(setTableData(data))}
            tableData={tableData}
            onRefreshChanged={(keys) => setChangedStoryKeys(new Set(keys))}
            onNewStoriesDetected={(keys) => setNewStoryKeys(new Set(keys))}
            onProjectSelected={(project) => setSelectedProject(project)}
            onImportLoadingChange={setImportLoading}
          />
        </div>

        {importLoading && (
          <div style={{ animation: "fadeSlideIn 0.3s ease forwards" }}>
            <div className="tg-section-header">
              <div className="tg-section-num green">2</div>
              <div style={{ flex: 1 }}>
                <div className="tg-section-title">Sanitised Stories</div>
                <div className="tg-section-subtitle">
                  Importing and sanitising stories…
                </div>
              </div>
            </div>
            <div className="tg-section-body" style={{ padding: "10px 12px" }}>
              <Skeleton active title={false} paragraph={{ rows: 6 }} />
            </div>
          </div>
        )}

        {showStories && !importLoading && (
          <div
            style={{
              animation: "fadeSlideIn 0.3s ease forwards",
            }}
          >
            <div className="tg-section-header">
              <div className="tg-section-num green">2</div>
              <div style={{ flex: 1 }}>
                <div className="tg-section-title">Sanitised Stories</div>
                <div className="tg-section-subtitle">
                  Regex-based technical sanitisation applied. Review before
                  proceeding.
                  {missingFieldsCount > 0 && (
                    <span
                      style={{
                        marginLeft: 8,
                        color: "#b91c1c",
                        fontWeight: 600,
                      }}
                    >
                      · {missingFieldsCount}{" "}
                      {missingFieldsCount === 1 ? "story" : "stories"} with
                      missing fields
                    </span>
                  )}
                </div>
              </div>
              {canRequestApproval && (
                <button
                  className="tg-btn tg-btn-ghost tg-btn-sm"
                  type="button"
                  onClick={() => setSendForApprovalOpen(true)}
                  // Gate on what would actually be submitted, not on the raw
                  // selection — approved/in-review rows stay selected but are
                  // filtered out of `approvalEpics`.
                  disabled={approvalEpics.length === 0 || !selectedProject}
                  style={{
                    opacity:
                      approvalEpics.length === 0 || !selectedProject ? 0.5 : 1,
                    whiteSpace: "nowrap",
                  }}
                >
                  <UserOutlined style={{ fontSize: 11 }} />
                  Send for Approval
                </button>
              )}
            </div>
            <div className="tg-section-body" style={{ padding: "10px 12px" }}>
              <div className="tg-auto-sanitised">
                <div className="tg-auto-sanitised-dot" />
                Auto-sanitised &nbsp;·&nbsp; PII patterns, credentials, and
                client identifiers removed
              </div>

              <div className="tg-stories-ant-table">
                <AITable
                  rowKey="storyId"
                  columns={columns}
                  datasource={flattenedStories}
                  showPagination={false}
                  rowClassName={(record: TableRow) => {
                    if (record.isEpic) {
                      return "tg-epic-row";
                    }
                    const isChanged = changedStoryKeys.has(record.storyId);
                    const isNew = newStoryKeys.has(record.storyId);
                    if (isChanged || isNew) {
                      return "tg-row-changed";
                    }
                    return "";
                  }}
                  expandable={{
                    rowExpandable: (record: TableRow) => !record.isEpic,
                    expandRowByClick: true,
                    showExpandColumn: false,
                    expandedRowKeys,
                    onExpand: handleRowExpand,
                    expandedRowRender: (record: TableRow) => {
                      if (record.isEpic) return null;

                      if (
                        editingStoryId === record.storyId &&
                        editingDraft &&
                        editingOriginal
                      ) {
                        return (
                          <InlineStoryEditor
                            original={editingOriginal}
                            draft={editingDraft}
                            onChange={setEditingDraft}
                            onSave={handleSaveEdit}
                            onCancel={handleCancelEdit}
                          />
                        );
                      }

                      const raw: string[] = record.acceptanceCriteria ?? [];
                      const criteria = raw.flatMap((c) =>
                        c.split(" | ").map((s) => s.trim()),
                      );
                      const edited = storyChanges.get(record.storyId);
                      const fieldLabels: Record<string, string> = {
                        storyTitle: "Title",
                        description: "Description",
                        acceptanceCriteria: "Acceptance Criteria",
                      };

                      return (
                        <div style={{ padding: "10px 24px 10px 40px" }}>
                          <div
                            style={{
                              fontSize: 12,
                              fontWeight: 500,
                              color: "#6b7280",
                              marginBottom: 6,
                            }}
                          >
                            Acceptance Criteria
                          </div>
                          {criteria.length === 0 ? (
                            <span style={{ fontSize: 12, color: "#9ca3af" }}>
                              No acceptance criteria defined.
                            </span>
                          ) : (
                            <ul
                              style={{
                                margin: 0,
                                paddingLeft: 18,
                                fontSize: 12,
                                color: "#374151",
                                lineHeight: "1.7",
                              }}
                            >
                              {criteria.map((c, i) => (
                                <li key={`${i}:${c}`}>{c}</li>
                              ))}
                            </ul>
                          )}

                          {edited && edited.length > 0 && (
                            <div className="tg-story-diff">
                              <div className="tg-story-diff-header">
                                <EditOutlined />
                                Story was edited before generation &mdash;{" "}
                                {edited.length}{" "}
                                {edited.length === 1 ? "field" : "fields"}{" "}
                                changed
                              </div>
                              {edited.map((change) => (
                                <div
                                  key={change.field}
                                  className="tg-diff-field"
                                >
                                  <div className="tg-diff-field-name">
                                    {fieldLabels[change.field] ?? change.field}
                                  </div>
                                  <div className="tg-diff-row">
                                    <div className="tg-diff-before">
                                      <span className="tg-diff-label">
                                        Before (imported)
                                      </span>
                                      {change.before || (
                                        <em style={{ opacity: 0.5 }}>Empty</em>
                                      )}
                                    </div>
                                    <div className="tg-diff-after">
                                      <span className="tg-diff-label">
                                        After (edited)
                                      </span>
                                      {change.after || (
                                        <em style={{ opacity: 0.5 }}>Empty</em>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    },
                  }}
                  rowSelection={{
                    // An approved story is selectable like any other so it can be
                    // sent for re-review after an edit. The tick therefore means
                    // "the user chose this", never "this is approved" — the Status
                    // column carries that. Only in-review rows are locked, since a
                    // second pending request for the same pair is rejected anyway.
                    selectedRowKeys: [...selectedStoryIds],

                    getCheckboxProps: (record: TableRow) => {
                      if (record.isEpic) return { disabled: true };
                      return { disabled: inReviewStoryIds.has(record.storyId) };
                    },

                    onChange: (keys: React.Key[]) => {
                      setSelectedStoryIds(
                        new Set(
                          keys
                            .map(String)
                            .filter(
                              (key) =>
                                !key.startsWith("epic-") &&
                                !inReviewStoryIds.has(key),
                            ),
                        ),
                      );
                    },

                    renderCell: (
                      checked: boolean,
                      record: TableRow,
                      index: number,
                      originNode: React.ReactNode,
                    ) => {
                      if (record.isEpic) return null;
                      if (inReviewStoryIds.has(record.storyId)) {
                        return (
                          <Tooltip title="Already sent for approval">
                            <Checkbox
                              disabled
                              style={{ cursor: "not-allowed" }}
                            />
                          </Tooltip>
                        );
                      }
                      return originNode;
                    },

                    columnTitle: () => {
                      const allSelected =
                        selectableStoryIds.length > 0 &&
                        selectableStoryIds.every((id) =>
                          selectedStoryIds.has(id),
                        );

                      const someSelected =
                        !allSelected &&
                        selectableStoryIds.some((id) =>
                          selectedStoryIds.has(id),
                        );

                      return (
                        <Checkbox
                          checked={allSelected}
                          indeterminate={someSelected}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedStoryIds(new Set(selectableStoryIds));
                            } else {
                              setSelectedStoryIds(new Set());
                            }
                          }}
                        />
                      );
                    },
                  }}
                />
              </div>
            </div>

            {tableData.length > EPICS_PER_PAGE && (
              <div className="tg-epic-pagination">
                <Pagination
                  current={epicPage}
                  total={tableData.length}
                  pageSize={EPICS_PER_PAGE}
                  onChange={handleEpicPageChange}
                  size="small"
                  showSizeChanger={false}
                  showTotal={(total, range) =>
                    `Epics ${range[0]}–${range[1]} of ${total}`
                  }
                />
              </div>
            )}

            <div className={`tg-review-banner ${state}`}>
              <div className="tg-review-banner-left">
                {isApproved ? (
                  <CheckCircleFilled
                    className={`tg-review-banner-icon ${state}`}
                  />
                ) : (
                  <UserOutlined className={`tg-review-banner-icon ${state}`} />
                )}
                <div className="tg-review-banner-text">
                  <span className={`tg-review-banner-title ${state}`}>
                    {isApproved ? "Stories Approved" : "Approval Required"}
                  </span>
                  <span className={`tg-review-banner-subtitle ${state}`}>
                    {isApproved
                      ? `${effectiveApprovedStoryIds.size} stories reviewed and approved. You can now attach context and generate.`
                      : "Stories must be sent for approval and approved by a reviewer before test cases can be generated."}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {showContext && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              animation: "fadeSlideIn 0.3s ease forwards",
            }}
          >
            <ContextDocumentsSection
              docs={contextDocuments}
              onFilesSelected={handleContextFilesSelected}
              onRemove={handleRemoveDoc}
              uploadingFileNames={uploadingFileNames}
              selectedProject={selectedProject}
              onAddExistingDocs={handleAddExistingDocs}
            />
            <ImpactPromptSection
              open={impactPromptOpen}
              impactPromptText={impactPrompt}
              onToggle={() => setImpactPromptOpen((current) => !current)}
              onChange={(value) => dispatch(setImpactPrompt(value))}
            />
            <GenerationSettingsPanel
              settings={generationSettings}
              onSettingsChange={onGenerationSettingsChange}
            />
          </div>
        )}

        {showBanner && (
          <div style={{ animation: "fadeSlideIn 0.3s ease forwards" }}>
            <ApprovalBanner
              selectedCount={effectiveApprovedStoryIds.size}
              totalCount={allStories.length}
              selectedApprovedCount={selectedApprovedStories.length}
              onGenerate={() => submitGeneration(false)}
              onRegenerate={() => submitGeneration(true)}
              isGenerated={isGenerated}
              isProcessing={isProcessing}
              canGenerate={canGenerate}
              cooldown={cooldown}
              disabledReason={generateHelpText}
            />
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "4px 2px",
            fontSize: 11.5,
            color: "#6b7280",
          }}
        >
          {isFileUploaded && (
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  background: "#f59e0b",
                  borderRadius: "50%",
                  display: "inline-block",
                }}
              />
              {allStories.length} stories imported
            </span>
          )}
          {showContext && (
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  background: "#10b981",
                  borderRadius: "50%",
                  display: "inline-block",
                }}
              />
              {contextDocuments.length} context docs
            </span>
          )}
          {showBanner && !canGenerate && (
            <span style={{ color: "#dc2626" }}>{generateHelpText}</span>
          )}
        </div>
      </div>

      <SendForApprovalModal
        open={sendForApprovalOpen}
        onClose={() => setSendForApprovalOpen(false)}
        epics={approvalEpics}
        projectId={selectedProject?.id ?? ""}
        onSubmitted={() => {
          // Optimistically flip the submitted stories to "In Review" so the badge
          // and re-selection block update now, not only after a re-import.
          const submittedIds = approvalEpics.flatMap((epic) =>
            epic.user_stories.map((story) => story.storyId),
          );
          dispatch(markStoriesInReview(submittedIds));
          setSendForApprovalOpen(false);
          setSelectedStoryIds(new Set());
        }}
      />
    </div>
  );
}
