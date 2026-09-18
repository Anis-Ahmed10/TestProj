"use client";

import React, { useCallback, useEffect, useState, useMemo } from "react";
import { App, Breadcrumb, Spin } from "antd";
import { HomeOutlined } from "@ant-design/icons";
import Link from "next/link";
import { Programme } from "@/types/programme";
import { Project } from "@/types/project";
import { getProgrammeById } from "@/services/programmeService";
import {
  formatProjectStartDate,
  getProjectStatusConfig,
} from "@/utils/projects/projectHelpers";
import { setActiveProgrammeId } from "@/utils/navContext";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

import "../../assets/css/clients.css";
import "@/app/(protected)/clients/programme/assets/css/programme.css";
import "../assets/css/project.css";

import OverviewTab from "./tabs/OverviewTab";
import AIToolsTab from "./tabs/AIToolsTab";
import JiraIntegrationTab from "./tabs/JiraIntegrationTab";
import DocumentsTab from "./tabs/DocumentsTab";
import TeamTab from "./tabs/TeamTab";
import LogsTab from "./tabs/LogsTab";
import { TabId, PROJECT_TABS } from "@/types/project";
import FolderIcon from "../assets/icons/FolderIcon";

interface ProjectPageProps {
  clientName: string;
  programmeId: string;
  projectId: string;
}

export default function ProjectPage({
  clientName,
  programmeId,
  projectId,
}: ProjectPageProps) {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const [project, setProject] = useState<Project | null>(null);
  const [programme, setProgramme] = useState<Programme | null>(null);
  const [clientDisplayName, setClientDisplayName] = useState(clientName);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  // Filter available tabs strictly by server authority
  const availableTabs = useMemo(() => {
    return PROJECT_TABS.filter((tab) => {
      if (tab.id === "logs") return hasPermission(PERMISSIONS.LOGS_READ);
      return true;
    });
  }, [hasPermission]);

  const loadProject = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setClientDisplayName(clientName);
      const prog = await getProgrammeById(programmeId);
      setProgramme(prog);
      const found = prog.projects.find((p) => p.id === projectId);
      if (!found) {
        setPageError("Project not found.");
      } else {
        setProject(found);
      }
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Failed to load project details.";
      setPageError(msg);
      message.error({ key: "project-load-error", content: msg });
    } finally {
      setLoading(false);
    }
  }, [clientName, programmeId, projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const resolvedProgrammeId = programme?.id ?? programmeId;
  const programmeDisplayName = programme?.name ?? programmeId;
  const projectDisplayName = project?.name ?? projectId;

  const {
    label: statusLabel,
    pillClass,
    dotClass,
  } = project
    ? getProjectStatusConfig(project.status)
    : { label: "", pillClass: "", dotClass: "" };

  const breadcrumbItems = [
    {
      title: (
        <Link href="/clients" className="workspace__breadcrumb-link">
          <HomeOutlined className="breadcrumb-icon" />
          Clients
        </Link>
      ),
    },
    {
      title: (
        <Link
          href={`/clients/workspace?clientName=${encodeURIComponent(
            clientName,
          )}`}
          className="workspace__breadcrumb-link"
        >
          {clientDisplayName}
        </Link>
      ),
    },
    {
      title: (
        <Link
          href={`/clients/programme?clientName=${encodeURIComponent(
            clientName,
          )}&programmeName=${encodeURIComponent(programmeDisplayName)}`}
          className="workspace__breadcrumb-link"
          onClick={() => setActiveProgrammeId(resolvedProgrammeId)}
        >
          {programmeDisplayName}
        </Link>
      ),
    },
    {
      title: (
        <span className="workspace__breadcrumb-current">
          {projectDisplayName}
        </span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="workspace">
        <div className="workspace__loading">
          <Spin size="large" description="Loading Project..." />
        </div>
      </div>
    );
  }

  if (pageError && !project) {
    return (
      <div className="workspace">
        <div className="workspace__breadcrumb-bar">
          <Breadcrumb items={breadcrumbItems} separator="›" />
        </div>
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Failed to load project</p>
          <p className="workspace__error-text">{pageError}</p>
          <Link
            href={`/clients/programme?clientName=${encodeURIComponent(
              clientName,
            )}&programmeName=${encodeURIComponent(programmeDisplayName)}`}
            className="workspace__back-link"
            onClick={() => setActiveProgrammeId(resolvedProgrammeId)}
          >
            ← Back to {programmeDisplayName}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace">
      <div className="workspace__breadcrumb-bar">
        <Breadcrumb items={breadcrumbItems} separator="›" />
      </div>

      <div className="workspace__header project-header">
        <div className="project-header-left">
          <div className="project-icon-container">
            <FolderIcon />
          </div>
          <div>
            <h1 className="project-title">{projectDisplayName}</h1>
            {project && (
              <div className="project-meta">
                <span className="project-meta-text">{clientDisplayName}</span>
                <span className="project-meta-separator">·</span>
                <span className="project-meta-text">
                  {programmeDisplayName}
                </span>
                {project.startDate && (
                  <>
                    <span className="project-meta-separator">·</span>
                    <span className="project-meta-text">
                      Started {formatProjectStartDate(project.startDate)}
                    </span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        {project && (
          <div className="project-status-wrapper">
            <span className={`project-status-pill ${pillClass}`}>
              <span className={`project-status-dot ${dotClass}`} />
              {statusLabel}
            </span>
          </div>
        )}
      </div>

      {/* ── Tabs ── */}
      <div className="project-view-tabs project-view-tabs--spaced">
        {availableTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`project-view-tab${
              activeTab === tab.id ? " project-view-tab--active" : ""
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab Content ── */}
      {activeTab === "overview" && <OverviewTab projectId={projectId} />}

      {activeTab === "ai-tools" && (
        <AIToolsTab projectId={projectId} projectName={projectDisplayName} />
      )}

      {activeTab === "jira-integration" && (
        <JiraIntegrationTab projectId={projectId} />
      )}

      {activeTab === "documents" && (
        <DocumentsTab
          folderPath={`${clientDisplayName}/${programmeDisplayName}/${projectDisplayName}`}
          entityId={projectId}
        />
      )}

      {activeTab === "team" && <TeamTab projectId={projectId} />}

      {activeTab === "logs" && <LogsTab projectId={projectId} />}
    </div>
  );
}
