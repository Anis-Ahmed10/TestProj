"use client";

import React, { useCallback, useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Spin, Breadcrumb } from "antd";
import { Programme } from "@/types/programme";
import { Project } from "@/types/project";
import {
  getProgrammeById,
  listProgrammesByClientId,
} from "@/services/programmeService";
import { getClientByName } from "@/services/clientsService";
import {
  formatProjectStartDate,
  getProjectStatusConfig,
} from "@/utils/projects/projectHelpers";
import {
  getActiveProgrammeId,
  getActiveProjectId,
  setActiveProgrammeId,
  setActiveProjectId,
} from "@/utils/navContext";

import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

import "@/app/(protected)/clients/assets/css/clients.css";
import "@/app/(protected)/clients/programme/assets/css/programme.css";
import "@/app/(protected)/clients/project/assets/css/project.css";

import OverviewTab from "../../clients/project/components/tabs/OverviewTab";
import AIToolsTab from "../../clients/project/components/tabs/AIToolsTab";
import JiraIntegrationTab from "../../clients/project/components/tabs/JiraIntegrationTab";
import DocumentsTab from "../../clients/project/components/tabs/DocumentsTab";
import TeamTab from "../../clients/project/components/tabs/TeamTab";
import LogsTab from "../../clients/project/components/tabs/LogsTab";
import { TabId, PROJECT_TABS } from "@/types/project";
import FolderIcon from "../../clients/project/assets/icons/FolderIcon";

export default function ProjectViewPage() {
  const searchParams = useSearchParams();
  const clientName = searchParams.get("clientName") ?? "";
  const programmeNameParam = searchParams.get("programmeName") ?? "";
  const projectNameParam = searchParams.get("projectName") ?? "";

  const { hasPermission } = usePermissions();

  const [project, setProject] = useState<Project | null>(null);
  const [programme, setProgramme] = useState<Programme | null>(null);
  const [programmeId, setProgrammeId] = useState<string>("");
  const [clientDisplayName, setClientDisplayName] = useState(clientName);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  // Determine if the user has access to project logs
  const canViewLogs = useMemo(() => {
    return hasPermission(PERMISSIONS.LOGS_READ);
  }, [hasPermission]);

  // Filter available tabs
  const availableTabs = useMemo(() => {
    return PROJECT_TABS.filter((tab) => {
      if (tab.id === "logs") return canViewLogs;
      return true;
    });
  }, [canViewLogs]);

  // Fallback to overview if a user loses permission or direct accesses logs tab
  useEffect(() => {
    if (activeTab === "logs" && !canViewLogs) {
      setActiveTab("overview");
    }
  }, [activeTab, canViewLogs]);

  const resolveProgrammeId = useCallback(async (): Promise<string> => {
    const client = await getClientByName(clientName);
    const stored = getActiveProgrammeId();
    if (stored) {
      try {
        const prog = await getProgrammeById(stored);
        if (prog.name === programmeNameParam && prog.clientId === client.id) {
          return stored;
        }
      } catch {}
    }
    const programmes = await listProgrammesByClientId(client.id);
    const match = programmes.find((p) => p.name === programmeNameParam);
    if (!match) {
      throw new Error(`Programme "${programmeNameParam}" was not found.`);
    }
    return match.id;
  }, [clientName, programmeNameParam]);

  const loadProject = useCallback(async () => {
    if (!clientName || !programmeNameParam || !projectNameParam) return;
    setLoading(true);
    setPageError(null);
    try {
      const [resolvedProgrammeId] = await Promise.all([
        resolveProgrammeId(),
        getClientByName(clientName)
          .then((c) => setClientDisplayName(c.name))
          .catch(() => {}),
      ]);
      setProgrammeId(resolvedProgrammeId);
      setActiveProgrammeId(resolvedProgrammeId);

      const prog = await getProgrammeById(resolvedProgrammeId);
      setProgramme(prog);

      const found =
        prog.projects.find((p) => p.name === projectNameParam) ??
        prog.projects.find((p) => p.id === getActiveProjectId());

      if (!found) {
        setPageError("Project not found.");
      } else {
        setProject(found);
        setActiveProjectId(found.id);
      }
    } catch (err) {
      setPageError(
        err instanceof Error ? err.message : "Failed to load project details.",
      );
    } finally {
      setLoading(false);
    }
  }, [clientName, programmeNameParam, projectNameParam, resolveProgrammeId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const programmeDisplayName = programme?.name ?? programmeNameParam;
  const projectDisplayName = project?.name ?? projectNameParam;

  const {
    label: statusLabel,
    pillClass,
    dotClass,
  } = project
    ? getProjectStatusConfig(project.status)
    : { label: "", pillClass: "", dotClass: "" };

  if (!clientName || !programmeNameParam || !projectNameParam) {
    return (
      <div className="workspace">
        <div className="workspace__empty workspace__empty--top">
          <div className="workspace__empty-icon">📋</div>
          <p className="workspace__empty-title">No project selected</p>
          <p className="workspace__empty-text">
            Click on a project from the{" "}
            <Link href="/clients" className="project-page__detail-link">
              Clients
            </Link>{" "}
            section to view its details here.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="workspace">
        <div className="workspace__loading">
          <Spin size="large" description="Loading project…" />
        </div>
      </div>
    );
  }

  if (pageError && !project) {
    return (
      <div className="workspace">
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Failed to load project</p>
          <p className="workspace__error-text">{pageError}</p>
          <Link href="/clients" className="workspace__back-link">
            ← Back to Clients
          </Link>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="workspace">
        <div className="workspace__loading">
          <Spin size="large" description="Loading project…" />
        </div>
      </div>
    );
  }

  return (
    <div className="workspace">
      {/* ── Breadcrumb ── */}
      <div className="workspace__breadcrumb-bar">
        <Breadcrumb
          separator="›"
          items={[
            {
              title: (
                <Link href="/clients" className="workspace__breadcrumb-link">
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
                  onClick={() => setActiveProgrammeId(programmeId)}
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
          ]}
        />
      </div>
      <div className="workspace__header project-header">
        <div className="project-header-left">
          <div className="project-icon-container">
            <FolderIcon />
          </div>
          <div>
            <h1 className="project-title">{projectDisplayName}</h1>
            <div className="project-meta">
              <span className="project-meta-text">{clientDisplayName}</span>
              <span className="project-meta-separator">·</span>
              <span className="project-meta-text">{programmeDisplayName}</span>
              {project.startDate && (
                <>
                  <span className="project-meta-separator">·</span>
                  <span className="project-meta-text">
                    Started {formatProjectStartDate(project.startDate)}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="project-status-wrapper">
          <span className={`project-status-pill ${pillClass}`}>
            <span className={`project-status-dot ${dotClass}`} />
            {statusLabel}
          </span>
        </div>
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
      {activeTab === "overview" && <OverviewTab projectId={project.id} />}

      {activeTab === "ai-tools" && (
        <AIToolsTab projectId={project.id} projectName={projectDisplayName} />
      )}

      {activeTab === "jira-integration" && (
        <JiraIntegrationTab projectId={project.id} />
      )}

      {activeTab === "documents" && (
        <DocumentsTab
          folderPath={`${clientDisplayName}/${programmeDisplayName}/${projectDisplayName}`}
          entityId={project.id}
        />
      )}

      {activeTab === "team" && <TeamTab projectId={project.id} />}

      {activeTab === "logs" && canViewLogs && (
        <LogsTab projectId={project.id} />
      )}
    </div>
  );
}
