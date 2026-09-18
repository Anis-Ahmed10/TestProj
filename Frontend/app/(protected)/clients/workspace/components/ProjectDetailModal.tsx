"use client";

import React from "react";
import { EditOutlined, InboxOutlined } from "@ant-design/icons";
import { Modal, Button } from "antd";
import { Project } from "@/types/project";
import {
  formatProjectStartDate,
  getProjectStatusConfig,
} from "@/utils/projects/projectHelpers";
import { formatISODate } from "@/utils/programmes/programmeHelpers";

interface ProjectDetailModalProps {
  project: Project;
  programmeName: string;
  onClose: () => void;
  onEdit?: (project: Project) => void;
  onArchive?: (project: Project) => void;
}

export default function ProjectDetailModal({
  project,
  programmeName,
  onClose,
  onEdit,
  onArchive,
}: ProjectDetailModalProps) {
  const { label, pillClass, dotClass } = getProjectStatusConfig(project.status);

  return (
    <Modal
      open
      title={
        <div>
          <div>{project.name}</div>
          <div style={{ fontSize: 13, fontWeight: 400, color: "#666" }}>
            Programme: <strong>{programmeName}</strong>
          </div>
        </div>
      }
      onCancel={onClose}
      className="proj-detail-modal"
      footer={[
        <Button
          key="archive"
          icon={<InboxOutlined />}
          disabled
          title="Archive this project (coming soon)"
          onClick={() => onArchive?.(project)}
        >
          Archive
        </Button>,
        <div key="spacer" style={{ flex: 1 }} />,
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
        <Button
          key="edit"
          type="primary"
          icon={<EditOutlined />}
          disabled
          title="Edit this project (coming soon)"
          onClick={() => onEdit?.(project)}
        >
          Edit
        </Button>,
      ]}
    >
      <div className="modal_body proj-detail-modal__body">
        {/* Info grid */}
        <div className="proj-detail-modal__grid">
          <div className="proj-detail-modal__row">
            <span className="proj-detail-modal__label">Status</span>
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {label}
            </span>
          </div>

          <div className="proj-detail-modal__row">
            <span className="proj-detail-modal__label">Start Date</span>
            <span className="proj-detail-modal__value">
              {formatProjectStartDate(project.startDate)}
            </span>
          </div>

          <div className="proj-detail-modal__row">
            <span className="proj-detail-modal__label">Created</span>
            <span className="proj-detail-modal__value">
              {formatISODate(project.createdAt)}
            </span>
          </div>

          <div className="proj-detail-modal__row">
            <span className="proj-detail-modal__label">Last Modified</span>
            <span className="proj-detail-modal__value">
              {formatISODate(project.lastModified)}
            </span>
          </div>

          {project.description && (
            <div className="proj-detail-modal__row proj-detail-modal__row--full">
              <span className="proj-detail-modal__label">Description</span>
              <span className="proj-detail-modal__value proj-detail-modal__value--desc">
                {project.description}
              </span>
            </div>
          )}
        </div>

        {/* Future features notice */}
        <div className="proj-detail-modal__future-banner">
          <span className="proj-detail-modal__future-dot" />
          Edit and Archive features are coming soon.
        </div>
      </div>
    </Modal>
  );
}
