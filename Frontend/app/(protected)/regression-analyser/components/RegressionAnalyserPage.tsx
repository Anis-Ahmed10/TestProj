"use client";

import React, {
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
} from "react";
import { App, Select, Spin } from "antd";
import InputPanel from "./InputPanel";
import OutputPanel from "./OutputPanel";
import PanelNav, { PanelView } from "@/components/PanelNav";
import {
  runRegressionAnalysis,
  setProjectId,
  setStories,
  selectChangeType,
  setChangeTypeDetail,
  setStrategy,
  setSuiteSource,
  setChangeDescription,
  setImpactPrompt,
  type RunRegressionAnalysisRejection,
} from "@/store/slices/regressionAnalyserSlice";
import "../assets/css/regressionAnalyser.css";
import { BackendProject } from "@/types/project";
import {
  fetchProjects,
  fetchProjectUserStories,
} from "@/services/projectService";
import { useAppDispatch, useAppSelector } from "@/store/store";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useActionCooldown } from "@/hooks/useActionCooldown";
import { AI_COOLDOWN_SERVICE } from "@/types/aiCooldown";

export default function RegressionAnalyzerPage() {
  const { message } = App.useApp();
  const dispatch = useAppDispatch();
  const {
    status,
    result,
    lastUpdated,
    inputState: {
      projectId,
      stories,
      changeType,
      changeTypeDetail,
      strategy,
      suiteSource,
      changeDescription,
      impactPrompt,
    },
  } = useAppSelector((state) => state.regressionAnalyser);
  const isAnalyzing = status === "inProgress";
  const cooldown = useActionCooldown(AI_COOLDOWN_SERVICE.REGRESSION_ANALYZER);

  const [activeView, setActiveView] = useState<PanelView>("input");
  const canViewOutput = result !== null || isAnalyzing;

  const {
    data: projectsData,
    loading: projectsLoading,
    error: projectsError,
  } = useAsyncData<BackendProject[]>(fetchProjects, []);
  const projects = projectsData ?? [];

  useEffect(() => {
    if (projectsError) {
      message.error(`Could not load projects: ${projectsError}`);
    }
  }, [projectsError, message]);

  const selectedProjectObj = useMemo(
    () => projects.find((p) => String(p.id) === projectId) ?? null,
    [projects, projectId],
  );

  const thunkPromiseRef = useRef<{ abort: () => void } | null>(null);

  useEffect(() => {
    return () => {
      thunkPromiseRef.current?.abort();
    };
  }, []);

  type StoryOption = { value: string; label: string };

  useEffect(() => {
    if (projectsLoading) return;
    if (projectsError) return;
    if (projectId && !selectedProjectObj) {
      dispatch(setProjectId(null));
    }
  }, [projectsLoading, projectsError, projectId, selectedProjectObj, dispatch]);

  const {
    data: storyOptionsData,
    loading: storiesLoading,
    error: storiesError,
    reload: retryLoadStories,
  } = useAsyncData<StoryOption[]>(
    () =>
      fetchProjectUserStories(selectedProjectObj!.id).then((fetched) =>
        fetched.map((s) => ({
          value: s.storyId,
          label: `${s.storyId} — ${s.title}`,
        })),
      ),
    [selectedProjectObj?.id],
    selectedProjectObj !== null,
  );
  const storyOptions = storyOptionsData ?? [];

  const canAnalyze = selectedProjectObj !== null;
  const handleProjectChange = useCallback(
    (value: string | null) => {
      thunkPromiseRef.current?.abort();
      thunkPromiseRef.current = null;
      dispatch(setProjectId(value));
    },
    [dispatch],
  );

  const handleAnalyze = useCallback(async () => {
    if (!canAnalyze) return;
    if (cooldown.isCoolingDown) return;

    setActiveView("output");

    try {
      const thunkPromise = dispatch(runRegressionAnalysis());
      thunkPromiseRef.current = thunkPromise;
      await thunkPromise.unwrap();

      cooldown.refresh();
    } catch (err) {
      const name = (err as { name?: string } | null)?.name;
      if (name === "AbortError" || name === "ConditionError") {
        return;
      }
      const rejection = err as RunRegressionAnalysisRejection | undefined;
      if (rejection?.code === "MISSING_PROJECT") {
        message.warning("Select a project before analysing.");
        return;
      }
      if (rejection?.code === "MISSING_CHANGE_TYPE") {
        message.warning("Select a change type before analysing.");
        return;
      }
      if (rejection?.code === "MISSING_STORIES") {
        message.warning("Select at least one story before analysing.");
        return;
      }
      message.error(
        typeof err === "string"
          ? err
          : "Failed to analyse impact. Please try again.",
      );
    }
  }, [canAnalyze, cooldown.isCoolingDown, cooldown.refresh, dispatch, message]);

  const projectOptions = useMemo(
    () =>
      projects.map((p) => ({
        value: String(p.id),
        label: `${p.client_name} - ${p.programme_name} - ${p.name}`,
      })),
    [projects],
  );
  const handleChangeDescriptionChange = useCallback(
    (value: string) => dispatch(setChangeDescription(value)),
    [dispatch],
  );
  const handleImpactPromptChange = useCallback(
    (value: string) => dispatch(setImpactPrompt(value)),
    [dispatch],
  );
  const handleStrategyChange = useCallback(
    (value: typeof strategy) => dispatch(setStrategy(value)),
    [dispatch],
  );
  const handleStoriesChange = useCallback(
    (value: string[]) => dispatch(setStories(value)),
    [dispatch],
  );
  const handleChangeTypeChange = useCallback(
    (value: typeof changeType) => dispatch(selectChangeType(value)),
    [dispatch],
  );
  const handleChangeTypeDetailChange = useCallback(
    (value: string) => dispatch(setChangeTypeDetail(value)),
    [dispatch],
  );
  const handleSuiteSourceChange = useCallback(
    (value: typeof suiteSource) => dispatch(setSuiteSource(value)),
    [dispatch],
  );

  return (
    <div className="ra-page">
      {/* ── Project selector bar ───────────────────────────────────────── */}
      <div className="ra-project-bar">
        <div className="ra-project-bar-label">Select Project</div>
        <Select
          id="ra-project-select-header"
          className="ra-project-bar-select"
          size="large"
          placeholder={
            projectsLoading ? "Loading projects…" : "Select a project"
          }
          value={projectsLoading ? undefined : projectId ?? undefined}
          onChange={(value) => handleProjectChange(value ?? null)}
          options={projectOptions}
          optionFilterProp="label"
          showSearch
          allowClear
          loading={projectsLoading}
          disabled={projectsLoading || isAnalyzing}
          notFoundContent={
            projectsLoading ? <Spin size="small" /> : "No projects found"
          }
          suffixIcon={<span className="ra-project-bar-icon">▾</span>}
        />
      </div>

      {/* ── input/output navigation*/}
      <PanelNav
        activeView={activeView}
        onChangeView={setActiveView}
        canViewOutput={canViewOutput}
        classPrefix="ra"
      />

      {/* ── input/output panels ────────── */}
      <div className={`ra-body ${activeView === "output" ? "single" : "solo"}`}>
        <div
          className={`ra-view ${
            activeView === "input" ? "" : "ra-view-hidden"
          }`}
        >
          <InputPanel
            changeDescription={changeDescription}
            onChangeDescriptionChange={handleChangeDescriptionChange}
            impactPrompt={impactPrompt}
            onImpactPromptChange={handleImpactPromptChange}
            selectedProjectObj={selectedProjectObj}
            canAnalyze={canAnalyze}
            isAnalyzing={isAnalyzing}
            onAnalyze={handleAnalyze}
            strategy={strategy}
            onStrategyChange={handleStrategyChange}
            stories={stories}
            onStoriesChange={handleStoriesChange}
            storyOptions={storyOptions}
            storiesLoading={storiesLoading}
            storiesError={storiesError}
            onRetryLoadStories={retryLoadStories}
            changeType={changeType}
            onChangeTypeChange={handleChangeTypeChange}
            changeTypeDetail={changeTypeDetail}
            onChangeTypeDetailChange={handleChangeTypeDetailChange}
            suiteSource={suiteSource}
            onSuiteSourceChange={handleSuiteSourceChange}
            isCoolingDown={cooldown.isCoolingDown}
            cooldownFormattedTime={cooldown.formatted}
          />
        </div>

        <div
          className={`ra-view ${
            activeView === "output" ? "" : "ra-view-hidden"
          }`}
        >
          <OutputPanel
            result={result}
            isAnalyzing={isAnalyzing}
            strategy={strategy}
            onReanalyse={handleAnalyze}
            canAnalyze={canAnalyze}
            canRunAnalysis={Boolean(changeType) && stories.length > 0}
            lastUpdated={lastUpdated}
            isCoolingDown={cooldown.isCoolingDown}
            projectName={selectedProjectObj?.name ?? ""}
          />
        </div>
      </div>
    </div>
  );
}
