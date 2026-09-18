"use client";

import React from "react";

interface CustomTestCaseCardProps {
  testCase: Record<string, unknown>;
  customFields: string[];
}

const EXCLUDED_KEYS = new Set(["testCaseId"]);

function formatLabel(key: string): string {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/[_-]/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim();
}

function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="tg-custom-field-null">—</span>;
  }

  if (typeof value === "boolean") {
    return (
      <span className={`tg-custom-field-bool ${value ? "true" : "false"}`}>
        {value ? "Yes" : "No"}
      </span>
    );
  }

  if (typeof value === "number") {
    return <span>{value}</span>;
  }

  if (typeof value === "string") {
    if (value.includes(";")) {
      const parts = value
        .split(";")
        .map((item) => item.trim())
        .filter(Boolean);
      if (parts.length > 1) {
        return (
          <ol className="tg-custom-field-list">
            {parts.map((item, idx) => (
              <li key={idx}>
                <span className="tg-custom-step-num">{idx + 1}</span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        );
      }
    }
    return <span>{value}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="tg-custom-field-null">—</span>;
    }

    return (
      <ol className="tg-custom-field-list">
        {value.map((item, idx) => (
          <li key={idx}>
            <span className="tg-custom-step-num">{idx + 1}</span>
            <span>
              {typeof item === "object" ? JSON.stringify(item) : String(item)}
            </span>
          </li>
        ))}
      </ol>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return <span className="tg-custom-field-null">—</span>;
    }

    return (
      <div className="tg-custom-field-object">
        {entries.map(([k, v]) => (
          <div key={k} className="tg-custom-field-object-entry">
            <span className="tg-custom-field-object-key">
              {formatLabel(k)}:
            </span>
            <span className="tg-custom-field-object-val">
              {typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

export default function CustomTestCaseCard({
  testCase,
  customFields,
}: CustomTestCaseCardProps) {
  // Build ordered keys: customFields first, then remaining keys
  const allKeys = Object.keys(testCase);
  const allKeysSet = new Set(allKeys);
  const customFieldsSet = new Set(customFields);

  const orderedKeys = [
    ...customFields.filter((f) => allKeysSet.has(f)),
    ...allKeys.filter((k) => !customFieldsSet.has(k)),
  ].filter((k) => !EXCLUDED_KEYS.has(k));

  if (orderedKeys.length === 0) {
    return <div className="tg-custom-card-empty">No fields to display.</div>;
  }

  return (
    <div className="tg-custom-card-fields">
      {orderedKeys.map((key) => (
        <div key={key} className="tg-custom-card-field">
          <div className="tg-custom-card-field-label">{formatLabel(key)}</div>
          <div className="tg-custom-card-field-value">
            {renderValue(testCase[key])}
          </div>
        </div>
      ))}
    </div>
  );
}
