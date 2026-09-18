"use client";

import { TestCaseLibraryRow as TestCase } from "@/types/testCaseLibrary";
import type { ReactNode } from "react";

function formatCustomFieldLabel(key: string): string {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/[_-]/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim();
}

function parseJsonIfPossible(val: string): unknown {
  const trimmed = val.trim();
  if (
    (trimmed.startsWith("[") && trimmed.endsWith("]")) ||
    (trimmed.startsWith("{") && trimmed.endsWith("}"))
  ) {
    try {
      return JSON.parse(val);
    } catch (e) {
      return val;
    }
  }
  return val;
}

function renderRichValue(key: string, value: unknown): ReactNode {
  if (value === null || value === undefined) {
    return <span className="tcl-custom-field-null">—</span>;
  }

  if (typeof value === "boolean") {
    return (
      <span className={`tcl-custom-field-bool ${value ? "true" : "false"}`}>
        {value ? "Yes" : "No"}
      </span>
    );
  }

  if (typeof value === "number") {
    return <span>{value}</span>;
  }

  if (typeof value === "string") {
    const parsed = parseJsonIfPossible(value);
    if (typeof parsed !== "string") {
      return renderRichValue(key, parsed);
    }

    const isListKey =
      /precondition|steps|scenario|action|result|instruction/i.test(key);
    let parts = value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (parts.length === 1 && value.includes(";")) {
      parts = value
        .split(";")
        .map((item) => item.trim())
        .filter(Boolean);
    }

    const bulletRegex = /^(?:\(?\d+\)?[\s.-]*|[-*]\s+)/;

    if (parts.length > 1 || isListKey) {
      const processedParts = parts.map((part) =>
        part.replace(bulletRegex, "").trim(),
      );
      return (
        <ul className="tcl-custom-list-items">
          {processedParts.map((item, idx) => (
            <li key={idx} className="tcl-custom-list-item">
              <span className="tcl-custom-step-num">{idx + 1}</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      );
    }

    return <span>{value}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="tcl-custom-field-null">—</span>;
    }

    return (
      <ul className="tcl-custom-list-items">
        {value.map((item, idx) => (
          <li key={idx} className="tcl-custom-list-item">
            <span className="tcl-custom-step-num">{idx + 1}</span>
            <span>
              {typeof item === "object" ? JSON.stringify(item) : String(item)}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return <span className="tcl-custom-field-null">—</span>;
    }

    return (
      <div className="tcl-custom-field-object">
        {entries.map(([k, v]) => (
          <div key={k} className="tcl-custom-field-object-entry">
            <span className="tcl-custom-field-object-key">
              {formatCustomFieldLabel(k)}:
            </span>
            <span className="tcl-custom-field-object-val">
              {typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

export function CustomTestCaseTab({ testCase }: { testCase: TestCase }) {
  const fields = testCase.customFields ?? {};
  // Exclude keys matching Title, testCaseKey, testcaseKey
  const EXCLUDED_KEYS = new Set(["title", "testcasekey"]);
  const entries = Object.entries(fields).filter(
    ([key]) => !EXCLUDED_KEYS.has(key.toLowerCase()),
  );

  if (entries.length === 0) {
    return (
      <section className="tcl-detail-section">
        <p className="tcl-muted">No custom fields available.</p>
      </section>
    );
  }

  return (
    <section className="tcl-detail-section">
      <div className="tcl-custom-list">
        {entries.map(([key, value]) => (
          <div className="tcl-custom-row" key={key}>
            <span className="tcl-custom-label">
              {formatCustomFieldLabel(key)}
            </span>
            <div className="tcl-custom-value-container">
              {renderRichValue(key, value)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
