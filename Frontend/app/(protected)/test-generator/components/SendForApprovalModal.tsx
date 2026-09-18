"use client";

import { useEffect, useState } from "react";
import { App, ConfigProvider, Modal, Select, Spin } from "antd";
import type { ProjectApprover } from "@/types/user";
import type {
  ApprovalEpic,
  StoryApprovalSkippedPair,
} from "@/types/storyApproval";
import { fetchProjectApprovers } from "@/services/userService";
import { submitStoriesForApproval } from "@/services/storyApprovalService";

const MAX_SKIPPED_PAIRS_SHOWN = 5;
const PROJECT_LEAD_LABEL = "Project Lead";

function formatSkippedPairs(pairs: StoryApprovalSkippedPair[]): string {
  const shown = pairs
    .slice(0, MAX_SKIPPED_PAIRS_SHOWN)
    .map((pair) => `${pair.user_story_id} (${pair.reviewer_email})`)
    .join(", ");
  const remaining = pairs.length - MAX_SKIPPED_PAIRS_SHOWN;
  return remaining > 0 ? `${shown}, +${remaining} more` : shown;
}

interface SendForApprovalModalProps {
  open: boolean;
  onClose: () => void;
  epics: ApprovalEpic[];
  projectId: string;
  onSubmitted: () => void;
}

export default function SendForApprovalModal({
  open,
  onClose,
  epics,
  projectId,
  onSubmitted,
}: SendForApprovalModalProps) {
  const { message } = App.useApp();

  const storyCount = epics.reduce(
    (total, epic) => total + epic.user_stories.length,
    0,
  );

  const [approvers, setApprovers] = useState<ProjectApprover[]>([]);
  const [approversLoading, setApproversLoading] = useState(true);
  const [approversFailed, setApproversFailed] = useState(false);
  const [selectedReviewerEmails, setSelectedReviewerEmails] = useState<
    string[]
  >([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open || !projectId) return;

    let cancelled = false;
    void fetchProjectApprovers(projectId)
      .then((data) => {
        if (cancelled) return;
        setApprovers(data);
        setSelectedReviewerEmails(
          data
            .filter((approver) => approver.role_label === PROJECT_LEAD_LABEL)
            .map((approver) => approver.email),
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setApproversFailed(true);
        message.error(
          err instanceof Error ? err.message : "Could not load approvers.",
        );
      })
      .finally(() => {
        if (!cancelled) setApproversLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, projectId, message]);

  const approverOptions = approvers.map((approver) => ({
    value: approver.email,
    label: approver.role_label
      ? `${approver.name} (${approver.email}) — ${approver.role_label}`
      : `${approver.name} (${approver.email})`,
  }));

  const emptyText = approversFailed
    ? "Could not load approvers"
    : "No Project Manager or Project Lead assigned";

  const reset = () => {
    setApprovers([]);
    setSelectedReviewerEmails([]);
    setApproversLoading(true);
    setApproversFailed(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    if (selectedReviewerEmails.length === 0 || storyCount === 0) return;

    try {
      setSubmitting(true);
      const result = await submitStoriesForApproval(
        epics,
        projectId,
        selectedReviewerEmails,
      );

      if (result.submitted_count > 0) {
        message.success(
          `Sent ${result.submitted_count} ${
            result.submitted_count === 1 ? "story" : "stories"
          } for approval.`,
        );
      }
      if (result.skipped_count > 0) {
        message.info(
          `${result.skipped_count} ${
            result.skipped_count === 1 ? "story was" : "stories were"
          } already pending approval: ${formatSkippedPairs(
            result.skipped_pairs,
          )}`,
        );
      }

      reset();
      onSubmitted();
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : "Failed to send for approval.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Send for Approval"
      open={open}
      onCancel={handleClose}
      onOk={handleSubmit}
      okText="Send"
      okButtonProps={{
        disabled: selectedReviewerEmails.length === 0 || storyCount === 0,
        loading: submitting,
      }}
      cancelButtonProps={{ disabled: submitting }}
    >
      <p style={{ marginBottom: 16 }}>
        Send {storyCount} {storyCount === 1 ? "story" : "stories"} for approval
      </p>

      <ConfigProvider
        theme={{
          token: {
            colorPrimary: "#1f3333",
            controlOutline: "rgba(31, 51, 51, 0.1)",
            controlItemBgActive: "#eef2f2",
          },
        }}
      >
        <Select
          mode="multiple"
          style={{ width: "100%" }}
          placeholder={
            approversLoading
              ? "Loading approvers…"
              : approverOptions.length
              ? "Select one or more reviewers"
              : emptyText
          }
          value={selectedReviewerEmails}
          onChange={setSelectedReviewerEmails}
          options={approverOptions}
          showSearch
          optionFilterProp="label"
          loading={approversLoading}
          disabled={approversLoading}
          notFoundContent={approversLoading ? <Spin size="small" /> : emptyText}
        />
      </ConfigProvider>
    </Modal>
  );
}
