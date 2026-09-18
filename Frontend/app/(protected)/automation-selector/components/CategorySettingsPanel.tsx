"use client";

import React, { useState, useCallback } from "react";
import {
  CloseOutlined,
  PlusOutlined,
  SettingOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { Modal, Input } from "antd";
import type {
  CategoryConfig,
  CategoryKey,
  ClassificationThresholds,
} from "@/types/automationCandidate";
import { PROMPT_VARIABLES } from "../mockData";

interface CategorySettingsPanelProps {
  open: boolean;
  categories: Record<CategoryKey, CategoryConfig>;
  categoryOrder: CategoryKey[];
  activeTab: CategoryKey;
  thresholds: ClassificationThresholds;
  projectContext: string;
  onClose: () => void;
  onTabChange: (key: CategoryKey) => void;
  onPromptChange: (
    key: CategoryKey,
    field: "basePrompt" | "impactPrompt",
    value: string,
  ) => void;
  onThresholdsChange: (t: ClassificationThresholds) => void;
  onProjectContextChange: (value: string) => void;
  onAddCategory: (name: string) => void;
  onSaveAndRerun: () => void;
}

export default function CategorySettingsPanel({
  open,
  categories,
  categoryOrder,
  activeTab,
  thresholds,
  projectContext,
  onClose,
  onTabChange,
  onPromptChange,
  onThresholdsChange,
  onProjectContextChange,
  onAddCategory,
  onSaveAndRerun,
}: CategorySettingsPanelProps) {
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");

  const handleAddCategory = useCallback(() => {
    const trimmed = newCategoryName.trim();
    if (!trimmed) return;
    onAddCategory(trimmed);
    setNewCategoryName("");
    setAddModalOpen(false);
  }, [newCategoryName, onAddCategory]);

  if (!open) return null;

  const activeCat = categories[activeTab];
  const vars = PROMPT_VARIABLES[activeTab] || PROMPT_VARIABLES.default;

  return (
    <>
      {/* Overlay */}
      <div className="as-settings-overlay" onClick={onClose} />

      {/* Panel */}
      <div className="as-settings-panel">
        {/* Header */}
        <div className="as-settings-panel-header">
          <h2>
            <SettingOutlined style={{ color: "var(--as-teal)" }} />
            Category Settings
          </h2>
          <button
            className="as-btn as-btn-ghost as-btn-sm"
            onClick={onClose}
            type="button"
          >
            <CloseOutlined />
          </button>
        </div>

        {/* Body */}
        <div className="as-settings-panel-body">
          {/* Category Tabs */}
          <div className="as-sp-cat-tab">
            {categoryOrder.map((key) => {
              const cat = categories[key];
              if (!cat) return null;
              return (
                <button
                  key={key}
                  className={activeTab === key ? "as-sp-tab-active" : ""}
                  onClick={() => onTabChange(key)}
                  type="button"
                >
                  {cat.title.replace(" Suite", "")}
                </button>
              );
            })}
          </div>

          {/* Per-category content */}
          {activeCat && (
            <>
              {/* Base Prompt */}
              <div className="as-sp-section">
                <label className="as-sp-label">Base Prompt</label>
                <textarea
                  className="as-sp-prompt"
                  rows={6}
                  value={activeCat.basePrompt}
                  onChange={(e) =>
                    onPromptChange(activeTab, "basePrompt", e.target.value)
                  }
                />
                <div className="as-sp-vars">
                  {vars.map((v) => (
                    <span key={v} className="as-sp-var">
                      {v}
                    </span>
                  ))}
                </div>
              </div>

              {/* Impact Prompt */}
              <div className="as-sp-section">
                <label className="as-sp-label">
                  Impact Prompt{" "}
                  <span className="as-sp-opt">
                    optional — TA context for this category
                  </span>
                </label>
                <textarea
                  className="as-sp-prompt"
                  rows={3}
                  placeholder="E.g. Prioritise API tests; our Playwright suite is not stable yet."
                  value={activeCat.impactPrompt}
                  onChange={(e) =>
                    onPromptChange(activeTab, "impactPrompt", e.target.value)
                  }
                />
              </div>

              {/* Scoring Factors */}
              <div className="as-sp-section">
                <label className="as-sp-label">Scoring Factors</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {activeCat.factors.map((f) => (
                    <span key={f} className="as-sp-factor-tag">
                      {f.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
                <div className="as-sp-factor-hint">
                  Factor weights are defined in the prompt file. Edit the base
                  prompt to adjust them.
                </div>
              </div>
            </>
          )}

          {/* Add category action */}
          <button
            className="as-sp-add-category"
            onClick={() => setAddModalOpen(true)}
            type="button"
          >
            <PlusOutlined style={{ color: "var(--as-teal)" }} />
            <span>Add custom category…</span>
          </button>

          {/* Classification Thresholds */}
          <div className="as-sp-threshold-section">
            <div className="as-sp-label">Classification Thresholds</div>
            <div className="as-sp-threshold-hint">
              These thresholds apply globally to all categories.
            </div>
            <div className="as-sp-threshold-row">
              <div className="as-sp-threshold">
                <div className="as-sp-th-label as-sp-th-label-auto">
                  Automate ≥
                </div>
                <input
                  type="number"
                  value={thresholds.automate}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(e) =>
                    onThresholdsChange({
                      ...thresholds,
                      automate: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div className="as-sp-threshold">
                <div className="as-sp-th-label as-sp-th-label-review">
                  Review ≥
                </div>
                <input
                  type="number"
                  value={thresholds.review}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(e) =>
                    onThresholdsChange({
                      ...thresholds,
                      review: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div className="as-sp-threshold">
                <div className="as-sp-th-label as-sp-th-label-manual">
                  Manual &lt;
                </div>
                <input
                  type="number"
                  value={thresholds.review}
                  min={0}
                  max={1}
                  step={0.05}
                  disabled
                />
              </div>
            </div>
          </div>

          {/* Project Context */}
          <div className="as-sp-context-section">
            <div className="as-sp-label">Project Context</div>
            <div className="as-sp-context-hint">
              Shared across all categories as{" "}
              <code className="as-sp-context-code">{"{project_context}"}</code>.
            </div>
            <textarea
              className="as-sp-prompt"
              rows={4}
              placeholder="Describe your team's automation stack, CI/CD setup, and current automation coverage…"
              value={projectContext}
              onChange={(e) => onProjectContextChange(e.target.value)}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="as-settings-panel-footer">
          <button
            className="as-btn as-btn-outline as-btn-sm"
            onClick={onClose}
            type="button"
          >
            Cancel
          </button>
          <button
            className="as-btn as-btn-filled as-btn-sm"
            onClick={onSaveAndRerun}
            type="button"
          >
            <SaveOutlined />
            Save &amp; Re-run
          </button>
        </div>
      </div>

      {/* Add Category Modal */}
      <Modal
        title="Add Custom Category"
        open={addModalOpen}
        onOk={handleAddCategory}
        onCancel={() => {
          setAddModalOpen(false);
          setNewCategoryName("");
        }}
        okText="Add"
        okButtonProps={{
          disabled: !newCategoryName.trim(),
          style: {
            background: "var(--as-teal)",
            borderColor: "var(--as-teal)",
          },
        }}
        destroyOnHidden
      >
        <div style={{ marginTop: 12 }}>
          <label
            className="as-sp-label"
            style={{ marginBottom: 8, display: "block" }}
          >
            Category Name
          </label>
          <Input
            className="as-add-modal-input"
            placeholder="e.g. Sanity, Performance, E2E…"
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
            onPressEnter={handleAddCategory}
            autoFocus
          />
        </div>
      </Modal>
    </>
  );
}
