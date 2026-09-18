"use client";

import React, { useRef, useState } from "react";
import { Button, Input, Select, Radio, Tag, App, ConfigProvider } from "antd";
import { SearchOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { BackendProject } from "@/types/project";
import { ContextDocumentRequest } from "@/types/testGenerator";
import {
  STRATEGIES,
  type ChangeType,
  type SuiteSource,
  type RegressionStrategy,
} from "@/types/impactAnalyzer";
import { ACCEPTED_FILE_TYPES } from "@/constants";
import {
  BrowseDocumentsModal,
  ContextDocumentsList,
  useContextDocumentUpload,
} from "@/components/ContextDocumentsPanel";
import type { UseActionCooldownResult } from "@/hooks/useActionCooldown";
import CooldownNotice from "@/components/CooldownNotice";

const { TextArea } = Input;

const tealTheme = {
  token: {
    colorPrimary: "#1f3333",
    controlOutline: "rgba(31, 51, 51, 0.1)",
    controlItemBgActive: "#eef2f2",
  },
};

// Backend caps the combined impactPrompt at 10,000 chars total
const CHANGE_TYPE_DETAIL_MAX_LENGTH = 3000;
const IMPACT_PROMPT_MAX_LENGTH = 4000;

const STRATEGY_OPTIONS = Object.entries(STRATEGIES).map(
  ([value, { label }]) => ({
    value,
    label,
  }),
);

interface InputPanelProps {
  changeDescription: string;
  onChangeDescriptionChange: (value: string) => void;
  impactPrompt: string;
  onImpactPromptChange: (value: string) => void;
  selectedProjectObj: BackendProject | null;
  canAnalyze: boolean;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  strategy: RegressionStrategy;
  onStrategyChange: (value: RegressionStrategy) => void;
  stories: string[];
  onStoriesChange: (value: string[]) => void;
  storyOptions: { value: string; label: string }[];
  storiesLoading: boolean;
  storiesError: string | null;
  onRetryLoadStories: () => void;
  changeType: ChangeType;
  onChangeTypeChange: (value: ChangeType) => void;
  changeTypeDetail: string;
  onChangeTypeDetailChange: (value: string) => void;
  suiteSource: SuiteSource;
  onSuiteSourceChange: (value: SuiteSource) => void;
  isCoolingDown: boolean;
  cooldownFormattedTime: string;
}

function InputPanel({
  changeDescription,
  onChangeDescriptionChange,
  impactPrompt,
  onImpactPromptChange,
  selectedProjectObj,
  canAnalyze,
  isAnalyzing,
  onAnalyze,
  strategy,
  onStrategyChange,
  stories,
  onStoriesChange,
  storyOptions,
  storiesLoading,
  storiesError,
  onRetryLoadStories,
  changeType,
  onChangeTypeChange,
  changeTypeDetail,
  onChangeTypeDetailChange,
  suiteSource,
  onSuiteSourceChange,
  isCoolingDown,
  cooldownFormattedTime,
}: InputPanelProps) {
  const { message } = App.useApp();
  const [contextDocs, setContextDocs] = useState<ContextDocumentRequest[]>([]);
  const [browseOpen, setBrowseOpen] = useState(false);
  const contextFileInputRef = useRef<HTMLInputElement>(null);

  const {
    uploadingFileNames,
    fetching,
    handleFilesSelected,
    handleRemoveDoc,
    handleAddExistingDocs,
  } = useContextDocumentUpload({
    selectedProject: selectedProjectObj,
    contextDocs,
    setContextDocs,
    autoFetch: true,
    onError: (msg) => message.error(msg),
    onNotice: (msg, kind) =>
      kind === "info" ? message.info(msg) : message.success(msg),
  });

  const changeTypeDetailPlaceholder: Record<
    Exclude<ChangeType, null>,
    string
  > = {
    defect:
      "e.g. Security patch in OTP validation logic, CVE-2026-1234. Only the 6-digit code verification path was changed.",
    feature:
      "e.g. Added biometric login via Face ID. Shares session token handling with password login flow.",
    config:
      "e.g. Database connection pool increased from 10 to 25. Redis cache TTL reduced to 5 minutes across all services.",
  };

  const projectLabel = selectedProjectObj
    ? `${selectedProjectObj.client_name} - ${selectedProjectObj.programme_name} - ${selectedProjectObj.name}`
    : null;

  return (
    <div className="ra-card ra-input-panel">
      <div className="ra-card-header ra-input-panel-header">
        <div>
          <h2 className="ra-card-title">Input — Change Details → LLM</h2>
        </div>
        <Tag color="blue" className="ra-side-tag">
          INPUT SIDE
        </Tag>
      </div>

      <div className="ra-card-body ra-steps-body">
        {/* Step 1 — Change Type */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--amber">1</div>
            <div>
              <div className="ra-step-title ra-step-title--required">
                Change Type
              </div>
              <div className="ra-step-subtitle">Select type</div>
            </div>
          </div>
          <div className="ra-step-content">
            <Radio.Group
              className="ra-change-type-group"
              value={changeType}
              onChange={(e) => {
                onChangeTypeChange(e.target.value);
                onChangeTypeDetailChange("");
              }}
            >
              {(
                [
                  { value: "defect", label: "Defect Fix", sub: "(Retesting)" },
                  {
                    value: "feature",
                    label: "Feature Change",
                    sub: "(Regression)",
                  },
                  {
                    value: "config",
                    label: "Config / Data Change",
                    sub: "(Regression)",
                  },
                ] as const
              ).map((opt) => (
                <div
                  key={opt.value}
                  className={`ra-ct-option ${
                    changeType === opt.value ? "ra-ct-option--active" : ""
                  }`}
                >
                  <Radio value={opt.value}>
                    {opt.label} <span className="ra-ct-sub">{opt.sub}</span>
                  </Radio>
                  {changeType === opt.value && (
                    <div className="ra-ct-detail">
                      <div className="ra-ct-detail-label">
                        Additional detail (optional)
                      </div>
                      <TextArea
                        rows={2}
                        placeholder={changeTypeDetailPlaceholder[opt.value]}
                        value={changeTypeDetail}
                        onChange={(e) =>
                          onChangeTypeDetailChange(e.target.value)
                        }
                        maxLength={CHANGE_TYPE_DETAIL_MAX_LENGTH}
                      />
                      <span className="ra-char-count">
                        {changeTypeDetail.length} /{" "}
                        {CHANGE_TYPE_DETAIL_MAX_LENGTH}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </Radio.Group>
          </div>
        </div>

        {/* Step 2 — Regression Suite */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--green">2</div>
            <div>
              <div className="ra-step-title">Regression Suite</div>
              <div className="ra-step-subtitle">
                Test suite to analyse against
              </div>
            </div>
          </div>
          <div className="ra-step-content">
            <Radio.Group
              className="ra-suite-source-group"
              value={suiteSource}
              onChange={(e) => onSuiteSourceChange(e.target.value)}
            >
              <div
                className={`ra-suite-source-option ${
                  suiteSource === "internal"
                    ? "ra-suite-source-option--active"
                    : ""
                }`}
                onClick={() => onSuiteSourceChange("internal")}
              >
                <Radio value="internal">
                  Internal test pool{" "}
                  <span className="ra-suite-source-sub">
                    (from Test Generator)
                  </span>
                </Radio>
                {suiteSource === "internal" && (
                  <div className="ra-suite-source-detail">
                    <div className="ra-frozen-suite">
                      <CheckCircleOutlined
                        className={
                          projectLabel
                            ? "ra-frozen-suite-icon--active"
                            : "ra-frozen-suite-icon--inactive"
                        }
                      />
                      <span>
                        {projectLabel
                          ? "Test cases from your internal test pool"
                          : "No project selected — choose one at the top of the page"}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div
                className={`ra-suite-source-option ${
                  suiteSource === "jira" ? "ra-suite-source-option--active" : ""
                }`}
                onClick={() => onSuiteSourceChange("jira")}
              >
                <Radio value="jira">Import from Jira test suite</Radio>
                {suiteSource === "jira" && (
                  <div className="ra-suite-source-detail">
                    <div className="ra-frozen-suite">
                      <CheckCircleOutlined
                        className={
                          projectLabel
                            ? "ra-frozen-suite-icon--active"
                            : "ra-frozen-suite-icon--inactive"
                        }
                      />
                      <span>
                        {projectLabel
                          ? "All test cases from the configured Jira suite"
                          : "No project selected — choose one at the top of the page"}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </Radio.Group>
          </div>
        </div>

        {/* Step 3 — Change Source */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--blue">3</div>
            <div>
              <div className="ra-step-title">Change Source</div>
              <div className="ra-step-subtitle">
                Select stories and/or describe the change
              </div>
            </div>
          </div>
          <div className="ra-step-content">
            <label className="ra-field-label ra-field-label--required">
              Stories (select one or more)
            </label>
            <ConfigProvider theme={tealTheme}>
              <Select
                mode="multiple"
                className="ra-select ra-select-stories"
                placeholder={
                  !selectedProjectObj
                    ? "Select a project first…"
                    : storiesLoading
                    ? "Loading stories…"
                    : "Search stories…"
                }
                value={stories}
                onChange={onStoriesChange}
                options={storyOptions}
                optionFilterProp="label"
                allowClear
                loading={storiesLoading}
                disabled={!selectedProjectObj}
                notFoundContent={
                  storiesLoading
                    ? "Loading…"
                    : storiesError
                    ? "Could not load stories"
                    : selectedProjectObj
                    ? "No approved user stories for this project"
                    : "Select a project first"
                }
              />
            </ConfigProvider>
            {storiesError && (
              <span className="ra-field-error">
                {storiesError}{" "}
                <Button type="link" size="small" onClick={onRetryLoadStories}>
                  Retry
                </Button>
              </span>
            )}

            <label className="ra-field-label ra-field-label--optional">
              Additional context about this change
            </label>
            <TextArea
              id="ra-change-description"
              className="ra-textarea"
              placeholder="e.g. All three stories share the OTP validation path which was refactored. Pay attention to shared session handling across login, password reset and transaction confirmation."
              rows={4}
              value={changeDescription}
              onChange={(e) => onChangeDescriptionChange(e.target.value)}
              maxLength={2000}
            />
            <span className="ra-char-count">
              {changeDescription.length} / 2000
            </span>
          </div>
        </div>

        {/* Step 4 — Regression Strategy */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--teal">4</div>
            <div>
              <div className="ra-step-title">Regression Strategy</div>
              <div className="ra-step-subtitle">
                How the AI should select test cases
              </div>
            </div>
          </div>
          <div className="ra-step-content">
            <label className="ra-field-label ra-field-label--required">
              Strategy
            </label>
            <ConfigProvider theme={tealTheme}>
              <Select
                className="ra-select"
                value={strategy}
                onChange={(value) => onStrategyChange(value)}
                options={STRATEGY_OPTIONS}
              />
            </ConfigProvider>
          </div>
        </div>

        {/* Step 5 — Context Documents (shared with Test Generator) */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--teal">5</div>
            <div>
              <div className="ra-step-title">Context Documents</div>
              <div className="ra-step-subtitle">
                Additional context for the AI
              </div>
            </div>
          </div>
          <div className="ra-step-content">
            <input
              ref={contextFileInputRef}
              type="file"
              accept={ACCEPTED_FILE_TYPES.join(",")}
              multiple
              className="ra-hidden-input"
              onChange={(e) => {
                handleFilesSelected(e.target.files);
                if (contextFileInputRef.current) {
                  contextFileInputRef.current.value = "";
                }
              }}
            />
            <ContextDocumentsList
              docs={contextDocs}
              uploadingFileNames={uploadingFileNames}
              fetching={fetching}
              selectedProject={selectedProjectObj}
              onRemove={handleRemoveDoc}
              onAddClick={() => contextFileInputRef.current?.click()}
              onBrowseClick={() => setBrowseOpen(true)}
              itemClassName="ra-context-item"
              addButtonClassName="ra-add-context"
              addButtonDisabledClassName="ra-add-context ra-add-context--disabled"
            />
            <BrowseDocumentsModal
              open={browseOpen}
              onClose={() => setBrowseOpen(false)}
              selectedProject={selectedProjectObj}
              existingDocumentIds={
                new Set(
                  contextDocs
                    .map((d) => d.documentId)
                    .filter(Boolean) as string[],
                )
              }
              onAdd={handleAddExistingDocs}
            />
          </div>
        </div>

        {/* Step 6 — Your Observations */}
        <div className="ra-step">
          <div className="ra-step-header">
            <div className="ra-step-num ra-step-num--blue">6</div>
            <div>
              <div className="ra-step-title">Your Observations</div>
              <div className="ra-step-subtitle">
                Additional notes for the AI
              </div>
            </div>
          </div>
          <div className="ra-step-content">
            <label className="ra-field-label ra-field-label--optional">
              Impact Prompt
            </label>
            <TextArea
              rows={3}
              placeholder="e.g., 'This change impacts the OTP flow which is shared across login, password reset and transaction confirmation. Pay special attention to downstream payment flows.'"
              value={impactPrompt}
              onChange={(e) => onImpactPromptChange(e.target.value)}
              maxLength={IMPACT_PROMPT_MAX_LENGTH}
            />
            <span className="ra-char-count">
              {impactPrompt.length} / {IMPACT_PROMPT_MAX_LENGTH}
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="ra-input-panel-footer">
        <div className="ra-status-bar">
          <span className="ra-status-item">
            <span
              className={`ra-status-dot ${
                canAnalyze ? "ra-status-dot--amber" : "ra-status-dot--grey"
              }`}
            />
            {!canAnalyze
              ? "Select a project to begin"
              : stories.length === 0
              ? "Select at least one story"
              : !changeType
              ? "Select a change type"
              : isCoolingDown
              ? undefined
              : "Ready to analyse"}
          </span>
          {isCoolingDown && (
            <CooldownNotice
              actionLabel="Regression Analysis"
              formattedTime={cooldownFormattedTime}
            />
          )}
        </div>
        <Button
          id="ra-analyze-btn"
          type="primary"
          icon={<SearchOutlined />}
          className="ra-analyze-btn"
          disabled={
            !canAnalyze || stories.length === 0 || !changeType || isCoolingDown
          }
          loading={isAnalyzing}
          onClick={onAnalyze}
        >
          {isAnalyzing ? "Processing…" : "Analyse Regression"}
        </Button>
      </div>
    </div>
  );
}
export default React.memo(InputPanel);
