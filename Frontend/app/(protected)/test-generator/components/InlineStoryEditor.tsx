"use client";

import { SaveOutlined } from "@ant-design/icons";

export interface EditDraft {
  storyTitle: string;
  description: string;
  acceptanceCriteria: string; // newline-separated for textarea
}

export default function InlineStoryEditor({
  original,
  draft,
  onChange,
  onSave,
  onCancel,
}: {
  original: EditDraft;
  draft: EditDraft;
  onChange: (d: EditDraft) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const titleMissing = !draft.storyTitle.trim();
  const descMissing = !draft.description.trim();
  const acMissing = !draft.acceptanceCriteria.trim();

  return (
    <div className="tg-inline-editor">
      <div className="tg-inline-editor-grid">
        <div>
          <div className="tg-inline-col-label">Original (imported)</div>
          <div className="tg-inline-original-box">
            <div className="tg-inline-original-field">
              <strong>Title</strong>
              {original.storyTitle || (
                <em style={{ color: "#d1d5db" }}>Empty</em>
              )}
            </div>
            <div className="tg-inline-original-field">
              <strong>Description</strong>
              {original.description || (
                <em style={{ color: "#d1d5db" }}>Empty</em>
              )}
            </div>
            <div className="tg-inline-original-field">
              <strong>Acceptance Criteria</strong>
              {original.acceptanceCriteria || (
                <em style={{ color: "#d1d5db" }}>Empty</em>
              )}
            </div>
          </div>
        </div>

        <div>
          <div className="tg-inline-col-label">Edit to complete</div>
          <div className="tg-inline-edit-fields">
            <div className="tg-inline-field-group">
              <label>
                Title
                {titleMissing && (
                  <span className="tg-required-label">Required</span>
                )}
              </label>
              <input
                type="text"
                value={draft.storyTitle}
                className={titleMissing ? "tg-field-error" : ""}
                onChange={(e) =>
                  onChange({ ...draft, storyTitle: e.target.value })
                }
                placeholder="Enter story title"
              />
            </div>
            <div className="tg-inline-field-group">
              <label>
                Description
                {descMissing && (
                  <span className="tg-required-label">Required</span>
                )}
              </label>
              <textarea
                rows={3}
                value={draft.description}
                className={descMissing ? "tg-field-error" : ""}
                onChange={(e) =>
                  onChange({ ...draft, description: e.target.value })
                }
                placeholder="As a [user], I want to… so that…"
              />
            </div>
            <div className="tg-inline-field-group">
              <label>
                Acceptance Criteria
                {acMissing && (
                  <span className="tg-required-label">Required</span>
                )}
              </label>
              <textarea
                rows={4}
                value={draft.acceptanceCriteria}
                className={acMissing ? "tg-field-error" : ""}
                onChange={(e) =>
                  onChange({ ...draft, acceptanceCriteria: e.target.value })
                }
                placeholder={"1. Given… When… Then…\n2. …"}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="tg-inline-edit-actions">
        <button className="tg-btn tg-btn-primary tg-btn-sm" onClick={onSave}>
          <SaveOutlined />
          Save
        </button>
        <button className="tg-btn-cancel-link" onClick={onCancel} type="button">
          Cancel
        </button>
      </div>
    </div>
  );
}
