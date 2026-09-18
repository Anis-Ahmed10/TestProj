"use client";

import { useState } from "react";
import { Upload } from "antd";
import type { UploadProps } from "antd";
import {
  InfoCircleOutlined,
  DownOutlined,
  UpOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import UploadCloudSVG from "../assets/UploadCloudSVG";

interface ExcelTabPanelProps {
  uploadProps: UploadProps;
  fileList: UploadProps["fileList"];
  isFileUploaded: boolean;
  isJiraImport: boolean;
  selectedProject: boolean;
}

const STRUCTURE_ROWS = [
  {
    label: "Title",
    desc: "Short, action-oriented name that captures the feature (e.g. View Payment History)",
  },
  {
    label: "User Story",
    desc: "As a [role], I want [goal], so that [benefit]",
  },
  {
    label: "Acceptance Criteria",
    desc: "Numbered list of testable conditions - each AC covers exactly one outcome",
  },
];

const TIPS = [
  "Each AC should describe one specific, observable outcome - not a group of behaviours",
  'Write ACs so a tester can clearly determine pass or fail - avoid vague terms like "works correctly"',
  "The role in the user story should reflect the real persona (student, admin, manager)",
  "Include enough context in the description for a tester to understand the full workflow",
];

export default function ExcelTabPanel({
  uploadProps,
  fileList,
  isFileUploaded,
  isJiraImport,
  selectedProject,
}: ExcelTabPanelProps) {
  const [guideOpen, setGuideOpen] = useState(false);

  return (
    <div className="usi-panel">
      <Upload
        {...uploadProps}
        fileList={fileList}
        maxCount={1}
        disabled={isJiraImport || selectedProject}
      >
        <div
          className={`usi-dropzone${isFileUploaded ? " uploaded" : ""}${
            isJiraImport || selectedProject ? " disabled" : ""
          }`}
        >
          <UploadCloudSVG />
          {isFileUploaded ? (
            <p className="usi-dropzone-text">
              File uploaded - remove it above to upload a different file
            </p>
          ) : (
            <>
              <p className="usi-dropzone-text">
                Drop your file here or{" "}
                <span className="usi-dropzone-link">click to browse</span>
              </p>
              <p className="usi-dropzone-formats">
                Supports .xlsx &nbsp;·&nbsp; .csv
              </p>
            </>
          )}
        </div>
      </Upload>

      <div className="usi-excel-columns">
        <span className="usi-col-label">Required columns</span>
        {[
          "Epic_ID",
          "Epic_Title",
          "Story_ID",
          "Story_Title",
          "Description",
          "Priority",
          "Acceptance_Criteria",
        ].map((col) => (
          <code key={col} className="usi-col-chip">
            {col}
          </code>
        ))}
      </div>

      <div className="usi-guide-wrap">
        <button
          className="usi-guide-header"
          onClick={() => setGuideOpen((o) => !o)}
          type="button"
        >
          <InfoCircleOutlined className="usi-guide-icon" />
          <span className="usi-guide-title">Story Guidelines</span>
          <span className="usi-guide-subtitle">
            What makes a good user story?
          </span>
          <span className="usi-guide-chevron">
            {guideOpen ? <UpOutlined /> : <DownOutlined />}
          </span>
        </button>

        {guideOpen && (
          <div className="usi-guide-body">
            <div className="usi-guide-section">
              <p className="usi-guide-section-label">Structure</p>
              <div className="usi-guide-structure">
                {STRUCTURE_ROWS.map(({ label, desc }) => (
                  <div key={label} className="usi-guide-struct-row">
                    <span className="usi-guide-struct-label">{label}</span>
                    <span className="usi-guide-struct-desc">{desc}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="usi-guide-section">
              <p className="usi-guide-section-label">Example</p>
              <div className="usi-guide-example">
                <p className="usi-guide-example-title">View Payment History</p>

                <div className="usi-guide-story-block">
                  <span className="usi-guide-story-line">
                    <span className="usi-guide-story-keyword">As a</span>{" "}
                    student,
                  </span>
                  <span className="usi-guide-story-line">
                    <span className="usi-guide-story-keyword">I want</span> to
                    view my payment history in the student portal,
                  </span>
                  <span className="usi-guide-story-line">
                    <span className="usi-guide-story-keyword">So that</span> I
                    can review my past payment transactions.
                  </span>
                </div>

                <div className="usi-guide-ac-list">
                  {[
                    {
                      id: "AC1",
                      title: "Navigate to Payment History",
                      body: "Student can navigate to the Finance section and open the Payment History page.",
                    },
                    {
                      id: "AC2",
                      title: "Display Payment Records",
                      body: "System displays records with: payment date, reference number, description, amount, payment method, and status.",
                    },
                    {
                      id: "AC3",
                      title: "Handle No Records",
                      body: 'If no records exist, the system displays a "no payment records available" message.',
                    },
                  ].map(({ id, title, body }) => (
                    <div key={id} className="usi-guide-ac-row">
                      <span className="usi-guide-ac-id">{id}</span>
                      <div>
                        <p className="usi-guide-ac-title">{title}</p>
                        <p className="usi-guide-ac-body">{body}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="usi-guide-section">
              <p className="usi-guide-section-label">Tips</p>
              <ul className="usi-guide-tips">
                {TIPS.map((tip, i) => (
                  <li key={i} className="usi-guide-tip-row">
                    <CheckCircleOutlined className="usi-guide-tip-icon" />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
