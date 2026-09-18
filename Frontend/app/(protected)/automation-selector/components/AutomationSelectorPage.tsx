"use client";

import React, {
  useCallback,
  useState,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { App, Select, Spin, Empty } from "antd";
import { SettingOutlined, SyncOutlined } from "@ant-design/icons";
import { useAppDispatch, useAppSelector } from "@/store/store";
import { BackendProject } from "@/types/project";
import { fetchProjects } from "@/services/projectService";
import {
  setProjectId,
  setActiveCategory,
  setSelectedFilter,
  setSearchQuery,
  setLevelFilter,
  toggleTestCaseChecked,
  setAllChecked,
  openSettingsPanel,
  closeSettingsPanel,
  setSettingsActiveTab,
  updateThresholds,
  updateProjectContext,
  updateCategoryPrompt,
  addCategory,
  runAutomationAnalysisAsync,
} from "@/store/slices/automationSelectionSlice";
import CategoryCards from "./CategoryCards";
import ResultsPanel from "./ResultsPanel";
import CategorySettingsPanel from "./CategorySettingsPanel";
import type {
  CategoryKey,
  ClassificationThresholds,
} from "@/types/automationCandidate";
import { useActionCooldown } from "@/hooks/useActionCooldown";
import { AI_COOLDOWN_SERVICE } from "@/types/aiCooldown";
import CooldownNotice from "@/components/CooldownNotice";

import "../assets/css/automationSelector.css";

export default function AutomationSelectorPage() {
  const { message } = App.useApp();
  const dispatch = useAppDispatch();

  const [projects, setProjects] = useState<BackendProject[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const runRef = useRef<{ abort: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProjectsLoading(true);
    fetchProjects()
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch((err) => {
        if (!cancelled) {
          message.error(
            err instanceof Error
              ? `Could not load projects: ${err.message}`
              : "Could not load projects. Please refresh the page.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setProjectsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [message]);

  const {
    categories,
    categoryOrder,
    activeCategory,
    selectedFilter,
    searchQuery,
    levelFilter,
    settingsPanelOpen,
    settingsActiveTab,
    thresholds,
    projectContext,
    lastRunTimestamp,
    rerunning,
    projectId,
    hasRun,
    status,
  } = useAppSelector((state) => state.automationSelection);

  const cooldown = useActionCooldown(AI_COOLDOWN_SERVICE.AUTOMATION_SELECTOR);
  const prevStatusRef = useRef(status);
  useEffect(() => {
    if (status === "success" && prevStatusRef.current !== "success") {
      cooldown.refresh();
    }
    prevStatusRef.current = status;
  }, [status, cooldown.refresh]);

  const projectOptions = useMemo(
    () =>
      projects.map((p) => ({
        value: String(p.id),
        label: `${p.client_name} - ${p.programme_name} - ${p.name}`,
      })),
    [projects],
  );

  const activeCat = categories[activeCategory];

  const handleSelectCategory = useCallback(
    (key: CategoryKey) => dispatch(setActiveCategory(key)),
    [dispatch],
  );

  const handleRun = useCallback(() => {
    if (rerunning || !projectId || cooldown.isCoolingDown) return;
    runRef.current = dispatch(runAutomationAnalysisAsync(projectId));
  }, [rerunning, projectId, dispatch, cooldown.isCoolingDown]);

  const handleCancelRun = useCallback(() => {
    runRef.current?.abort();
  }, []);

  const handleAddCategoryFromCards = useCallback(() => {
    dispatch(openSettingsPanel());
  }, [dispatch]);

  const handleAddCategory = useCallback(
    (name: string) => {
      const key = name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "");
      if (categories[key]) {
        message.warning(`Category "${name}" already exists.`);
        return;
      }
      dispatch(addCategory({ key, name }));
      message.success(
        `Category "${name}" added. The AI service scores its own configured categories, so this one stays empty until a prompt is added there.`,
      );
    },
    [categories, dispatch, message],
  );

  const handleOpenSettings = useCallback(
    () => dispatch(openSettingsPanel()),
    [dispatch],
  );
  const handleCloseSettings = useCallback(
    () => dispatch(closeSettingsPanel()),
    [dispatch],
  );
  const handleSettingsTabChange = useCallback(
    (key: CategoryKey) => dispatch(setSettingsActiveTab(key)),
    [dispatch],
  );
  const handlePromptChange = useCallback(
    (key: CategoryKey, field: "basePrompt" | "impactPrompt", value: string) =>
      dispatch(updateCategoryPrompt({ key, field, value })),
    [dispatch],
  );
  const handleThresholdsChange = useCallback(
    (t: ClassificationThresholds) => dispatch(updateThresholds(t)),
    [dispatch],
  );
  const handleProjectContextChange = useCallback(
    (value: string) => dispatch(updateProjectContext(value)),
    [dispatch],
  );

  const handleSaveAndRerun = useCallback(() => {
    dispatch(closeSettingsPanel());
    handleRun();
  }, [dispatch, handleRun]);

  const handleFilterChange = useCallback(
    (f: "all" | "automate" | "review" | "manual") =>
      dispatch(setSelectedFilter(f)),
    [dispatch],
  );
  const handleSearchChange = useCallback(
    (q: string) => dispatch(setSearchQuery(q)),
    [dispatch],
  );
  const handleLevelFilterChange = useCallback(
    (l: string) => dispatch(setLevelFilter(l)),
    [dispatch],
  );

  const handleToggleTestCase = useCallback(
    (id: string) => dispatch(toggleTestCaseChecked(id)),
    [dispatch],
  );
  const handleToggleAll = useCallback(
    (checked: boolean, visibleIds: string[]) =>
      dispatch(setAllChecked({ checked, visibleIds })),
    [dispatch],
  );

  return (
    <div className="as-page">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          flexShrink: 0,
        }}
      >
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 500, color: "#4B5563" }}>Project:</span>
          <Select
            style={{ width: "100%", maxWidth: 400 }}
            placeholder={
              projectsLoading ? "Loading projects…" : "Select a project"
            }
            value={projectId ?? undefined}
            onChange={(value) => dispatch(setProjectId(value ?? null))}
            options={projectOptions}
            optionFilterProp="label"
            showSearch
            allowClear
            loading={projectsLoading}
            disabled={projectsLoading || rerunning}
            notFoundContent={
              projectsLoading ? <Spin size="small" /> : "No projects found"
            }
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {lastRunTimestamp && (
            <span style={{ color: "#6B7280", fontSize: 12 }}>
              Last run: <strong>{lastRunTimestamp}</strong>
            </span>
          )}
          {cooldown.isCoolingDown && (
            <CooldownNotice
              actionLabel="Automation Analysis"
              formattedTime={cooldown.formatted}
            />
          )}
          <button
            className="as-btn as-btn-ghost as-btn-sm"
            onClick={handleOpenSettings}
            type="button"
            disabled={!hasRun}
          >
            <SettingOutlined />
            Category Settings
          </button>
          {rerunning && (
            <button
              className="as-btn as-btn-outline as-btn-sm"
              onClick={handleCancelRun}
              type="button"
            >
              Cancel
            </button>
          )}
          <button
            className="as-btn as-btn-filled as-btn-sm"
            onClick={handleRun}
            disabled={rerunning || !projectId || cooldown.isCoolingDown}
            type="button"
          >
            <SyncOutlined className={rerunning ? "as-spinning" : ""} />
            {rerunning ? "Analysing…" : hasRun ? "Re-run Analysis" : "Run"}
          </button>
        </div>
      </div>

      {!projectId || !hasRun ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#FFFFFF",
            borderRadius: 8,
            border: "1px solid #E5E7EB",
          }}
        >
          {rerunning ? (
            <Spin description="Analysing test cases for automation suitability…" />
          ) : (
            <Empty
              description={
                <span style={{ color: "#6B7280" }}>
                  {!projectId
                    ? "Select a project before running the Automation Selector."
                    : "Click 'Run' to execute the Automation Selector."}
                </span>
              }
            />
          )}
        </div>
      ) : (
        <>
          <CategoryCards
            categories={categories}
            categoryOrder={categoryOrder}
            activeCategory={activeCategory}
            onSelectCategory={handleSelectCategory}
            onAddCategory={handleAddCategoryFromCards}
          />

          {activeCat && (
            <ResultsPanel
              category={activeCat}
              selectedFilter={selectedFilter}
              searchQuery={searchQuery}
              levelFilter={levelFilter}
              onFilterChange={handleFilterChange}
              onSearchChange={handleSearchChange}
              onLevelFilterChange={handleLevelFilterChange}
              onToggleTestCase={handleToggleTestCase}
              onToggleAll={handleToggleAll}
            />
          )}
        </>
      )}

      <CategorySettingsPanel
        open={settingsPanelOpen}
        categories={categories}
        categoryOrder={categoryOrder}
        activeTab={settingsActiveTab}
        thresholds={thresholds}
        projectContext={projectContext}
        onClose={handleCloseSettings}
        onTabChange={handleSettingsTabChange}
        onPromptChange={handlePromptChange}
        onThresholdsChange={handleThresholdsChange}
        onProjectContextChange={handleProjectContextChange}
        onAddCategory={handleAddCategory}
        onSaveAndRerun={handleSaveAndRerun}
      />
    </div>
  );
}
