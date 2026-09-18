"use client";

import React from "react";

export type PanelView = "input" | "output";

interface PanelNavProps {
  activeView: PanelView;
  onChangeView: (view: PanelView) => void;
  canViewOutput: boolean;
  classPrefix: string;
  inputLabel?: string;
  outputLabel?: string;
}

export default function PanelNav({
  activeView,
  onChangeView,
  canViewOutput,
  classPrefix,
  inputLabel = "← Input",
  outputLabel = "Output →",
}: PanelNavProps) {
  return (
    <div className={`${classPrefix}-top-view-nav`}>
      <button
        type="button"
        className={`${classPrefix}-nav-btn ${classPrefix}-nav-btn-left ${
          activeView === "input" ? "active" : ""
        }`}
        onClick={() => onChangeView("input")}
      >
        {inputLabel}
      </button>

      <button
        type="button"
        className={`${classPrefix}-nav-btn ${classPrefix}-nav-btn-right ${
          activeView === "output" ? "active" : ""
        }`}
        onClick={() => onChangeView("output")}
        disabled={!canViewOutput}
      >
        {outputLabel}
      </button>
    </div>
  );
}
