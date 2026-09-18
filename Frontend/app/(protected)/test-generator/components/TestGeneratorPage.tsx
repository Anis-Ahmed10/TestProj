"use client";

import { useEffect, useState } from "react";

import { Spin } from "antd";

import InputPanel from "./inputPanel";
import OutputPanel from "./outputPanel";
import PanelNav, { PanelView } from "@/components/PanelNav";
import "../assets/css/inputPanel.css";
import {
  GenerationSettings,
  TestGeneratorRequest,
} from "@/types/testGenerator";
import {
  clearGenerationResult,
  generateTestCasesAsync,
  setWorkflowStep,
  setGenerationSettings,
  setHasInputFromPasteOrUpload,
} from "@/store/slices/testGenerationSlice";
import { useAppDispatch, useAppSelector } from "@/store/store";
import { useActionCooldown } from "@/hooks/useActionCooldown";
import { AI_COOLDOWN_SERVICE } from "@/types/aiCooldown";

export default function TestGeneratorPage() {
  const dispatch = useAppDispatch();
  const {
    status,
    generatedData,
    settings: reduxSettings,
    generatedSettings,
    workflowStep,
    inputState,
  } = useAppSelector((state) => state.testGeneration);

  const isProcessing = status === "inProgress";
  const isGenerated = workflowStep === "generated";
  const outputGenerationSettings = generatedSettings ?? reduxSettings;

  const cooldown = useActionCooldown(AI_COOLDOWN_SERVICE.TEST_GENERATOR);

  const [activeView, setActiveView] = useState<PanelView>(
    workflowStep === "generated" ? "output" : "input",
  );

  useEffect(() => {
    setActiveView(workflowStep === "generated" ? "output" : "input");
  }, [workflowStep]);

  const canViewOutput = isGenerated;

  useEffect(() => {
    if (status === "success" && generatedData && workflowStep !== "generated") {
      dispatch(setWorkflowStep("generated"));
    }
  }, [status, generatedData, workflowStep, dispatch]);

  const handleGenerate = async (request: TestGeneratorRequest) => {
    if (isProcessing || cooldown.isCoolingDown) {
      return;
    }

    dispatch(clearGenerationResult());

    if (workflowStep === "generated") {
      dispatch(setWorkflowStep("approved"));
    }

    try {
      await dispatch(generateTestCasesAsync(request)).unwrap();

      cooldown.refresh();

      // If generation completed and input was from Jira, ensure paste/upload flag cleared
      if (inputState.isJiraImport) {
        dispatch(setHasInputFromPasteOrUpload(false));
      }
    } catch {
      // Redux status is already "failed" — the global listener handles the notification.
    }
  };

  const handleRegenerate = async (request: TestGeneratorRequest) => {
    await handleGenerate(request);
  };

  return (
    <div
      className={`tg-dashboard ${isProcessing ? "tg-dashboard-loading" : ""}`}
    >
      <PanelNav
        activeView={activeView}
        onChangeView={setActiveView}
        canViewOutput={canViewOutput}
        classPrefix="tg"
      />

      <div className={`tg-body ${activeView === "output" ? "single" : "solo"}`}>
        <div
          className={`tg-view ${
            activeView === "input" ? "" : "tg-view-hidden"
          }`}
        >
          <InputPanel
            workflowStep={workflowStep}
            generationSettings={reduxSettings}
            onGenerationSettingsChange={(settings: GenerationSettings) =>
              dispatch(setGenerationSettings(settings))
            }
            onStoriesUploaded={() => dispatch(setWorkflowStep("review"))}
            onGenerate={handleGenerate}
            onRegenerate={handleRegenerate}
            isProcessing={isProcessing}
            cooldown={cooldown}
          />
        </div>

        <div
          className={`tg-view ${
            activeView === "output" ? "" : "tg-view-hidden"
          }`}
        >
          {isGenerated && (
            <OutputPanel
              generationSettings={outputGenerationSettings}
              generatedData={generatedData}
              isJiraImport={inputState.isJiraImport}
              disableJiraPush={inputState.hasInputFromPasteOrUpload}
            />
          )}
        </div>
      </div>

      {isProcessing && (
        <div className="tg-loading-overlay" role="status" aria-live="polite">
          <div className="tg-loading-card">
            <Spin size="large" />
            <div className="tg-loading-title">Generating Test Cases</div>
            <div className="tg-loading-subtitle">
              Waiting for backend result. Please do not refresh or change
              inputs.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
