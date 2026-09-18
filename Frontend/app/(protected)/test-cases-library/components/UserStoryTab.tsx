"use client";

import { TestCaseLibraryRow as TestCase } from "@/types/testCaseLibrary";

function parseDescription(desc: string) {
  // Match template patterns: "As a [role] I want to [action] So that [benefit]"
  const asAMatch = desc.match(/as\s+a\s+([\s\S]*?)(?=i\s+want|so\s+that|$)/i);
  const iWantMatch = desc.match(
    /i\s+want\s+(?:to\s+)?([\s\S]*?)(?=so\s+that|$)/i,
  );
  const soThatMatch = desc.match(/so(?:\s+that)?\s+([\s\S]*)/i);

  return {
    asA: asAMatch ? asAMatch[1].trim() : "",
    iWant: iWantMatch ? iWantMatch[1].trim() : "",
    soThat: soThatMatch ? soThatMatch[1].trim() : "",
  };
}

export function UserStoryTab({ testCase }: { testCase: TestCase }) {
  const parsed = testCase.storyDescription
    ? parseDescription(testCase.storyDescription)
    : null;
  const hasParsedTemplate =
    parsed && (parsed.asA || parsed.iWant || parsed.soThat);

  // Split acceptance criteria by pipe (|) or newline (\n)
  const acList = testCase.storyAcceptanceCriteria
    ? testCase.storyAcceptanceCriteria
        .split(/[|\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  return (
    <section className="tcl-story-tab-panel">
      <div className="tcl-story-card">
        {/* Header with Purple Tag and Title */}
        <div className="tcl-story-header">
          {testCase.storyKey && (
            <span className="tcl-story-key-badge">{testCase.storyKey}</span>
          )}
          <span className="tcl-story-title-text">{testCase.storyTitle}</span>
        </div>
        <hr className="tcl-story-divider" />

        {/* Story Details (AS A, I WANT, SO THAT) */}
        {testCase.storyDescription && (
          <div className="tcl-story-details">
            {hasParsedTemplate ? (
              <>
                {parsed.asA && (
                  <div className="tcl-story-detail-row">
                    <span className="tcl-story-detail-label">AS A</span>
                    <span className="tcl-story-detail-value">{parsed.asA}</span>
                  </div>
                )}
                {parsed.iWant && (
                  <div className="tcl-story-detail-row">
                    <span className="tcl-story-detail-label">I WANT</span>
                    <span className="tcl-story-detail-value">
                      {parsed.iWant}
                    </span>
                  </div>
                )}
                {parsed.soThat && (
                  <div className="tcl-story-detail-row">
                    <span className="tcl-story-detail-label">SO THAT</span>
                    <span className="tcl-story-detail-value">
                      {parsed.soThat}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div className="tcl-story-detail-row">
                <span className="tcl-story-detail-label">DESCRIPTION</span>
                <span className="tcl-story-detail-value">
                  {testCase.storyDescription}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Acceptance Criteria */}
      {acList.length > 0 && (
        <div className="tcl-ac-section">
          <h4 className="tcl-ac-heading">Acceptance Criteria</h4>
          <ul className="tcl-ac-list-vertical">
            {acList.map((criterion, i) => (
              <li key={i} className="tcl-ac-item-row">
                <span className="tcl-ac-checkmark">✓</span>
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Project & Epic context footer */}
      {(testCase.epicKey || testCase.projectName) && (
        <div className="tcl-story-meta-footer">
          {testCase.epicKey && (
            <div className="tcl-story-meta-item">
              Epic: <strong>{testCase.epicKey}</strong> {testCase.epicTitle}
            </div>
          )}
          {testCase.projectName && (
            <div className="tcl-story-meta-item">
              Project: <strong>{testCase.projectName}</strong>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
