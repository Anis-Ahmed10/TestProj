"use client";

import React from "react";
import { ExperimentOutlined } from "@ant-design/icons";
import type { AutomationTestCase } from "@/types/automationCandidate";

interface ExpandedRowDetailProps {
  record: AutomationTestCase;
}

export default function ExpandedRowDetail({ record }: ExpandedRowDetailProps) {
  return (
    <div className="as-expand-content">
      {/* LLM Reasoning */}
      <div className="as-reasoning-title">
        <ExperimentOutlined className="as-reasoning-title-icon" />
        LLM Reasoning
      </div>
      <ul className="as-reasoning-list">
        {record.reasoning.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      {/* Factor Scores */}
      <div className="as-factors-title">Factor Scores</div>
      <div className="as-factors-grid">
        {Object.entries(record.factors).map(([key, value]) => (
          <div key={key} className="as-factor-item">
            <div className="as-factor-name">{key.replace(/_/g, " ")}</div>
            <div className="as-factor-bar">
              <div className="as-factor-bar-bg">
                <div
                  className="as-factor-bar-fill"
                  style={{ width: `${Math.round(value * 100)}%` }}
                />
              </div>
              <div className="as-factor-bar-val">{value.toFixed(2)}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Decision Prompt */}
      {record.decisionPrompt && (
        <div className="as-decision-prompt-box">
          <div className="as-dp-label">⚑ TA Decision Required</div>
          <p>{record.decisionPrompt}</p>
        </div>
      )}

      {/* Rule Override */}
      {record.ruleOverride && (
        <div className="as-rule-override-box">
          <div className="as-ro-label">⛔ Hard Rule Override</div>
          <p>{record.ruleOverride}</p>
        </div>
      )}
    </div>
  );
}
