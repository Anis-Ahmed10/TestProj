"use client";

import React from "react";
import type { AutomationMixData } from "@/types/automationCandidate";

interface AutomationMixProps {
  mix: AutomationMixData;
}

const LEVEL_COLORS: Record<string, string> = {
  UNIT: "var(--as-purple)",
  API: "var(--as-blue)",
  UI: "var(--as-amber)",
};

const DEFAULT_COLORS = [
  "var(--as-green)",
  "var(--as-teal)",
  "var(--as-red)",
  "#ec4899", // pink
  "#14b8a6", // teal
  "#8b5cf6", // violet
];

export default function AutomationMix({ mix }: AutomationMixProps) {
  const levels = Object.keys(mix).sort();

  const getColor = (level: string, index: number) => {
    const key = level.toUpperCase();
    if (LEVEL_COLORS[key]) return LEVEL_COLORS[key];
    return DEFAULT_COLORS[index % DEFAULT_COLORS.length];
  };

  return (
    <div className="as-pyramid-row">
      <div className="as-pyramid-label">Automation Mix</div>

      <div className="as-pyramid-mini">
        {levels.map((level, index) => (
          <div className="as-pmb" key={level}>
            <div
              className="as-pmb-bar"
              style={{
                background: getColor(level, index),
                width: 50,
                height: Math.max(16, (mix[level].percent / 100) * 60),
              }}
            >
              {mix[level].percent}%
            </div>
            <div className="as-pmb-lbl">{level.toUpperCase()}</div>
          </div>
        ))}
      </div>

      <div className="as-pyramid-legend">
        {levels.map((level, index) => (
          <span className="as-pyramid-legend-item" key={level}>
            <span
              className="as-legend-dot"
              style={{ background: getColor(level, index) }}
            />
            {level.toUpperCase()}: {mix[level].selected} cases
          </span>
        ))}
      </div>
    </div>
  );
}
