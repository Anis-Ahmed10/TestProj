"use client";

import { TestCaseLibraryRow as TestCase } from "@/types/testCaseLibrary";
import { Tag } from "antd";

export function BddTestCaseTab({ testCase }: { testCase: TestCase }) {
  const scenario = testCase.scenario ?? { given: [], when: [], then: [] };

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

      <section className="tcl-scenario" aria-label="BDD scenario">
        <div className="tcl-scenario-box tcl-scenario-box--given">
          <h3>Given</h3>
          {scenario.given.map((line, i) => (
            <p key={i}>- {line}</p>
          ))}
        </div>
        <div className="tcl-scenario-box tcl-scenario-box--when">
          <h3>When</h3>
          {scenario.when.map((line, i) => (
            <p key={i}>- {line}</p>
          ))}
        </div>
        <div className="tcl-scenario-box tcl-scenario-box--then">
          <h3>Then</h3>
          {scenario.then.map((line, i) => (
            <p key={i}>- {line}</p>
          ))}
        </div>
      </section>

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
