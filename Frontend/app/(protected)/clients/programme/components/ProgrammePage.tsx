"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Breadcrumb, App, Spin, Input } from "antd";
import { HomeOutlined, PlusOutlined } from "@ant-design/icons";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import Link from "next/link";
import { Programme } from "@/types/programme";
import { Project } from "@/types/project";
import { getProgrammeById } from "@/services/programmeService";
import { getClientByName } from "@/services/clientsService";
import { listProgrammesByClientId } from "@/services/programmeService";
import ProjectCard from "../../workspace/components/ProjectCard";
import ProjectListView from "../../workspace/components/ProjectListView";
import AddProjectModal from "../../workspace/components/AddProjectModal";
import EditProjectModal from "../../workspace/components/EditProjectModal";
import DeleteProjectPopup from "../../workspace/components/DeleteProjectPopup";
import {
  formatISODate,
  getProgrammeStatusConfig,
} from "@/utils/programmes/programmeHelpers";
import "../../assets/css/clients.css";
import "../assets/css/programme.css";
import DocumentsSection from "@/app/(protected)/clients/components/DocumentsSection";
import { useDebounce } from "@/lib/useDebounce";
import { getActiveProgrammeId, setActiveProgrammeId } from "@/utils/navContext";

import ViewToggle, { ViewMode } from "@/components/ViewToggle";

interface ProgrammePageProps {
  clientName: string;
  programmeName: string;
}

export default function ProgrammePage({
  clientName,
  programmeName,
}: ProgrammePageProps) {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const canCreateProject = hasPermission(PERMISSIONS.PROJECT_CREATE);

  const [programme, setProgramme] = useState<Programme | null>(null);
  const [programmeId, setProgrammeId] = useState<string>("");
  const [clientDisplayName, setClientDisplayName] = useState(clientName);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("card");

  const [showAddProject, setShowAddProject] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  const [clientManager, setClientManager] = useState<string | undefined>(
    undefined,
  );

  const resolveProgrammeId = useCallback(
    async (client: { id: string; manager?: string }): Promise<string> => {
      const stored = getActiveProgrammeId();
      if (stored) {
        try {
          const prog = await getProgrammeById(stored);
          if (prog.name === programmeName && prog.clientId === client.id) {
            return stored;
          }
        } catch {}
      }
      const programmes = await listProgrammesByClientId(client.id);
      const match = programmes.find((p) => p.name === programmeName);
      if (!match) {
        throw new Error(`Programme "${programmeName}" was not found.`);
      }
      return match.id;
    },
    [programmeName],
  );

  const loadProgramme = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setClientDisplayName(clientName);
      const client = await getClientByName(clientName);
      setClientManager(client.manager);

      const resolvedId = await resolveProgrammeId(client);
      setProgrammeId(resolvedId);
      setActiveProgrammeId(resolvedId);
      const prog = await getProgrammeById(resolvedId);
      setProgramme(prog);
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Failed to load programme details.";
      setPageError(msg);
      message.error({ key: "programme-load-error", content: msg });
    } finally {
      setLoading(false);
    }
  }, [clientName, resolveProgrammeId, message]);

  useEffect(() => {
    loadProgramme();
  }, [loadProgramme]);

  const allProjects = programme?.projects ?? [];

  const filteredProjects = useMemo(() => {
    const q = debouncedSearchQuery.trim().toLowerCase();
    if (!q) return allProjects;
    return allProjects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q) ||
        p.status.toLowerCase().includes(q),
    );
  }, [allProjects, debouncedSearchQuery]);

  function handleProjectAdded(newProject: Project) {
    setProgramme((prev) =>
      prev ? { ...prev, projects: [...prev.projects, newProject] } : prev,
    );
    message.success(`Project "${newProject.name}" created successfully.`);
  }

  function handleProjectUpdated(updated: Project) {
    setProgramme((prev) =>
      prev
        ? {
            ...prev,
            projects: prev.projects.map((p) =>
              p.id === updated.id ? updated : p,
            ),
          }
        : prev,
    );
    message.success(`Project "${updated.name}" updated successfully.`);
  }

  function handleProjectDeleted(deletedId: string) {
    setProgramme((prev) =>
      prev
        ? { ...prev, projects: prev.projects.filter((p) => p.id !== deletedId) }
        : prev,
    );
    message.success("Project deleted successfully.");
  }

  const displayName = programme?.name ?? programmeName;

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
        <span className="workspace__breadcrumb-current">{displayName}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="workspace">
        <div className="workspace__loading">
          <Spin size="large" description="Loading programme…" />
        </div>
      </div>
    );
  }

  if (pageError && !programme) {
    return (
      <div className="workspace">
        <div className="workspace__breadcrumb-bar">
          <Breadcrumb items={breadcrumbItems} separator="›" />
        </div>
        <div className="workspace__error-state">
          <div className="workspace__error-icon">⚠</div>
          <p className="workspace__error-title">Failed to load programme</p>
          <p className="workspace__error-text">{pageError}</p>
          <Link
            href={`/clients/workspace?clientName=${encodeURIComponent(
              clientName,
            )}`}
            className="workspace__back-link"
          >
            ← Back to {clientDisplayName}
          </Link>
        </div>
      </div>
    );
  }

  const statusConfig = programme
    ? getProgrammeStatusConfig(programme.status)
    : null;

  const emptyMessage =
    searchQuery.trim() !== ""
      ? `No projects found matching "${searchQuery.trim()}"`
      : "No projects yet";
  const emptySubtext =
    searchQuery.trim() !== ""
      ? "Try a different search term."
      : "Create the first project to get started.";

  return (
    <div className="workspace">
      {/* Breadcrumb */}
      <div className="workspace__breadcrumb-bar">
        <Breadcrumb items={breadcrumbItems} separator="›" />
      </div>

      {/* Compact header */}
      <div className="workspace__compact-header">
        <h1 className="workspace__compact-title">{displayName}</h1>
      </div>

      {/* Programme Information */}
      {programme && (
        <div className="prog-info">
          <h2 className="prog-info__title">Programme Information</h2>
          <div className="prog-info__grid">
            <div className="prog-info__row">
              <span className="prog-info__label">Name</span>
              <span className="prog-info__value">{programme.name}</span>
            </div>
            <div className="prog-info__row">
              <span className="prog-info__label">Status</span>
              <span className="prog-info__value">
                {statusConfig && (
                  <span
                    className={`project-status-pill ${statusConfig.pillClass}`}
                  >
                    <span
                      className={`project-status-dot ${statusConfig.dotClass}`}
                    />
                    {statusConfig.label}
                  </span>
                )}
              </span>
            </div>
            <div className="prog-info__row">
              <span className="prog-info__label">Manager</span>
              <span className="prog-info__value">
                {programme.manager ?? clientManager ?? "Unassigned"}
              </span>
            </div>
            {programme.description && (
              <div className="prog-info__row prog-info__row--full">
                <span className="prog-info__label">Description</span>
                <span className="prog-info__value prog-info__value--desc">
                  {programme.description}
                </span>
              </div>
            )}
            <div className="prog-info__row">
              <span className="prog-info__label">Created</span>
              <span className="prog-info__value">
                {formatISODate(programme.createdAt)}
              </span>
            </div>
            <div className="prog-info__row">
              <span className="prog-info__label">Last Modified</span>
              <span className="prog-info__value">
                {formatISODate(programme.lastModified)}
              </span>
            </div>
          </div>
        </div>
      )}

      <DocumentsSection
        folderPath={`${clientDisplayName}/${displayName}`}
        entityId={programmeId}
      />

      {/* Section header: title + count, search, view toggle, add button — all on one line */}
      <div className="workspace__section-header workspace__section-header--spaced">
        <h2 className="workspace__section-title">
          Projects
          {allProjects.length > 0 && (
            <span className="workspace__section-count">
              {allProjects.length}
            </span>
          )}
          {debouncedSearchQuery.trim() && (
            <span className="workspace__section-count workspace__section-count--filtered">
              {filteredProjects.length} matching
            </span>
          )}
        </h2>

        <div className="workspace__section-actions">
          {allProjects.length > 0 && (
            <Input.Search
              allowClear
              placeholder="Search projects…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 240 }}
              aria-label="Search projects"
            />
          )}

          {allProjects.length > 0 && (
            <ViewToggle viewMode={viewMode} onChange={setViewMode} />
          )}

          {programme && canCreateProject && (
            <button
              className="programme-page__add-btn"
              onClick={() => setShowAddProject(true)}
            >
              <PlusOutlined className="btn-icon" />
              Create Project
            </button>
          )}
        </div>
      </div>

      <div className="workspace__body">
        {filteredProjects.length === 0 ? (
          <div className="workspace__empty">
            <div className="workspace__empty-icon">📂</div>
            <p className="workspace__empty-title">{emptyMessage}</p>
            <p className="workspace__empty-text">{emptySubtext}</p>
          </div>
        ) : viewMode === "card" ? (
          <div className="workspace__programmes">
            {filteredProjects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                clientName={clientName}
                programmeId={programmeId}
                programmeName={displayName}
                onEdit={(p) => setEditingProject(p)}
                onDelete={(p) => setDeletingProject(p)}
              />
            ))}
          </div>
        ) : (
          <ProjectListView
            projects={filteredProjects}
            clientName={clientName}
            programmeId={programmeId}
            onEdit={(p) => setEditingProject(p)}
            onDelete={(p) => setDeletingProject(p)}
          />
        )}
      </div>

      {showAddProject && programme && (
        <AddProjectModal
          programme={programme}
          existingNames={allProjects.map((p) => p.name)}
          onClose={() => setShowAddProject(false)}
          onProjectAdded={(project) => {
            handleProjectAdded(project);
            setShowAddProject(false);
          }}
        />
      )}

      {editingProject && programme && (
        <EditProjectModal
          project={editingProject}
          programme={programme}
          existingNames={allProjects
            .filter((p) => p.id !== editingProject.id)
            .map((p) => p.name)}
          onClose={() => setEditingProject(null)}
          onUpdated={(updated) => {
            handleProjectUpdated(updated);
            setEditingProject(null);
          }}
        />
      )}

      {deletingProject && (
        <DeleteProjectPopup
          project={deletingProject}
          onClose={() => setDeletingProject(null)}
          onDeleted={(deletedId) => {
            handleProjectDeleted(deletedId);
            setDeletingProject(null);
          }}
        />
      )}
    </div>
  );
}
