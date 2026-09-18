"use client";

import { TestCaseLibraryRow as TestCase } from "@/types/testCaseLibrary";
import { Tag } from "antd";

export function StandardTestCaseTab({ testCase }: { testCase: TestCase }) {
  return (
    <>
      {(testCase.preconditions ?? []).length > 0 && (
        <section className="tcl-detail-section">
          <h3>Preconditions</h3>
          <div className="tcl-chip-row">
            {(testCase.preconditions ?? []).map((item, i) => (
              <span className="tcl-chip" key={i}>
                {item}
              </span>
            ))}
          </div>
        </section>
      )}

      {(testCase.steps ?? []).length > 0 && (
        <section className="tcl-detail-section">
          <h3>Steps</h3>
          <ol className="tcl-steps">
            {(testCase.steps ?? []).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </section>
      )}

      {testCase.expectedResult && (
        <section className="tcl-detail-section">
          <h3>Expected Result</h3>
          <div className="tcl-result">{testCase.expectedResult}</div>
        </section>
      )}

      {testCase.testData && Object.keys(testCase.testData).length > 0 && (
        <section className="tcl-detail-section">
          <h3>Test Data</h3>
          <div className="tcl-chip-row">
            {Object.entries(testCase.testData).map(([key, value]) => (
              <span className="tcl-chip" key={key}>
                <strong>{key}:</strong>&nbsp;
                {typeof value === "string" ? value : JSON.stringify(value)}
              </span>
            ))}
          </div>
        </section>
      )}

      {(testCase.tags ?? []).length > 0 && (
        <div className="tcl-tag-row">
          {(testCase.tags ?? []).map((tag, i) => (
            <Tag key={i} color="purple">
              #{tag}
            </Tag>
          ))}
        </div>
      )}
    </>
  );
}
