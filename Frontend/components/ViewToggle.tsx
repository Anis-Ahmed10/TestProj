"use client";

import React from "react";
import { AppstoreOutlined, UnorderedListOutlined } from "@ant-design/icons";

export type ViewMode = "card" | "list";

interface ViewToggleProps {
  viewMode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export default function ViewToggle({
  viewMode,
  onChange,
}: Readonly<ViewToggleProps>) {
  return (
    <div
      className="clients-page__view-toggle"
      role="group"
      aria-label="View mode"
    >
      <button
        className={`clients-page__view-btn${
          viewMode === "card" ? " clients-page__view-btn--active" : ""
        }`}
        onClick={() => onChange("card")}
        aria-label="Card view"
        aria-pressed={viewMode === "card"}
      >
        <AppstoreOutlined />
      </button>
      <button
        className={`clients-page__view-btn${
          viewMode === "list" ? " clients-page__view-btn--active" : ""
        }`}
        onClick={() => onChange("list")}
        aria-label="List view"
        aria-pressed={viewMode === "list"}
      >
        <UnorderedListOutlined />
      </button>
    </div>
  );
}
