"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { App, Input, Select, Spin } from "antd";
import {
  PlusOutlined,
  RightOutlined,
  FolderOpenOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table/interface";

import AITable from "@/components/AITable";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import { useDebounce } from "@/lib/useDebounce";
import {
  fetchProjects,
  fetchProjectTestCaseSummary,
  ProjectTestCaseSummary,
} from "@/services/projectService";
import { BackendProject, PROJECT_STATUS_OPTIONS } from "@/types/project";
import {
  formatProjectStartDate,
  getProjectStatusConfig,
  normalizeProjectStatus,
} from "@/utils/projects/projectHelpers";
import { STATUS_LABELS } from "@/constants/status";
import { setActiveProgrammeId, setActiveProjectId } from "@/utils/navContext";
import CreateProjectModal from "./CreateProjectModal";

import "@/app/(protected)/clients/assets/css/clients.css";
import "@/app/(protected)/clients/project/assets/css/project.css";
import "../assets/css/activeProjects.css";

const ALL_CLIENTS = "All Clients";
const ALL_STATUSES = "";

type SortOption = "client" | "name" | "updated";

const SORT_LABELS: Record<SortOption, string> = {
  client: "Sort: Client Name",
  name: "Sort: Project Name",
  updated: "Sort: Last Updated",
};

interface ProjectRow extends BackendProject {
  testCases?: number;
  passRate?: number;
}

export default function ActiveProjectsPage() {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission(PERMISSIONS.PROJECT_CREATE);

  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [summaries, setSummaries] = useState<
    Record<string, ProjectTestCaseSummary>
  >({});
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  const [clientFilter, setClientFilter] = useState<string>(ALL_CLIENTS);
  const [statusFilter, setStatusFilter] = useState<string>(ALL_STATUSES);
  const [sortBy, setSortBy] = useState<SortOption>("client");

  const [showCreateModal, setShowCreateModal] = useState(false);

  const SUMMARY_FETCH_BATCH_SIZE = 8;

  async function fetchSummariesInBatches(
    projectIds: string[],
    isCancelled: () => boolean,
  ): Promise<Record<string, ProjectTestCaseSummary>> {
    const nextSummaries: Record<string, ProjectTestCaseSummary> = {};
    for (let i = 0; i < projectIds.length; i += SUMMARY_FETCH_BATCH_SIZE) {
      if (isCancelled()) break;
      const batch = projectIds.slice(i, i + SUMMARY_FETCH_BATCH_SIZE);
      const results = await Promise.allSettled(
        batch.map((id) => fetchProjectTestCaseSummary(id)),
      );
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          nextSummaries[batch[idx]] = result.value;
        }
      });
    }
    return nextSummaries;
  }

  async function loadProjects(isCancelled: () => boolean) {
    setLoading(true);
    try {
      const data = await fetchProjects();
      if (isCancelled()) return;
      setProjects(data);

      const nextSummaries = await fetchSummariesInBatches(
        data.map((p) => p.id),
        isCancelled,
      );
      if (isCancelled()) return;
      setSummaries(nextSummaries);
    } catch (error) {
      if (isCancelled()) return;
      message.error({
        key: "active-projects-load-error",
        content:
          error instanceof Error ? error.message : "Failed to load projects.",
      });
    } finally {
      if (!isCancelled()) setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    loadProjects(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, []);

  const clientOptions = useMemo(() => {
    const unique = Array.from(
      new Set(projects.map((p) => p.client_name).filter(Boolean)),
    );
    return [ALL_CLIENTS, ...unique];
  }, [projects]);

  const filteredProjects = useMemo(() => {
    const q = debouncedSearchQuery.trim().toLowerCase();

    const filtered = projects.filter((p) => {
      const matchClient =
        clientFilter === ALL_CLIENTS || p.client_name === clientFilter;
      const matchStatus =
        statusFilter === ALL_STATUSES ||
        normalizeProjectStatus(p.status ?? "active") === statusFilter;
      const matchSearch =
        q === "" ||
        p.name.toLowerCase().includes(q) ||
        p.client_name.toLowerCase().includes(q) ||
        p.programme_name.toLowerCase().includes(q);

      return matchClient && matchStatus && matchSearch;
    });

    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "updated") {
        const aTime = a.last_modified ? new Date(a.last_modified).getTime() : 0;
        const bTime = b.last_modified ? new Date(b.last_modified).getTime() : 0;
        return bTime - aTime;
      }
      return a.client_name.localeCompare(b.client_name);
    });

    return sorted;
  }, [projects, clientFilter, statusFilter, debouncedSearchQuery, sortBy]);

  function handleProjectCreated(project: BackendProject) {
    setProjects((prev) => [project, ...prev]);
    setShowCreateModal(false);
  }

  function projectViewHref(project: ProjectRow) {
    return `/project-view?clientName=${encodeURIComponent(
      project.client_name,
    )}&programmeName=${encodeURIComponent(
      project.programme_name,
    )}&projectName=${encodeURIComponent(project.name)}`;
  }

  function handleProjectRowClick(project: ProjectRow) {
    setActiveProgrammeId(project.programme_id);
    setActiveProjectId(project.id);
  }

  const columns: ColumnsType<ProjectRow> = [
    {
      title: "PROJECT",
      dataIndex: "name",
      key: "name",
      render: (_, record) => (
        <Link
          href={projectViewHref(record)}
          className="active-projects-table__project-link"
          onClick={() => handleProjectRowClick(record)}
        >
          {record.name}
        </Link>
      ),
    },
    {
      title: "CLIENT",
      dataIndex: "client_name",
      key: "client_name",
    },
    {
      title: "PROGRAMME",
      dataIndex: "programme_name",
      key: "programme_name",
    },
    {
      title: "STATUS",
      dataIndex: "status",
      key: "status",
      render: (_, record) => {
        const status = normalizeProjectStatus(record.status ?? "active");
        const { label, pillClass, dotClass } = getProjectStatusConfig(status);
        return (
          <span className={`project-status-pill ${pillClass}`}>
            <span className={`project-status-dot ${dotClass}`} />
            {label}
          </span>
        );
      },
    },
    {
      title: "TEST CASES",
      key: "testCases",
      render: (_, record) => summaries[record.id]?.total ?? "—",
    },
    {
      title: "PASS RATE",
      key: "passRate",
      render: (_, record) => {
        const rate = summaries[record.id]?.pass_rate;
        return rate === undefined ? "—" : `${Math.round(rate)}%`;
      },
    },
    {
      title: "TEAM",
      key: "team",
      render: () => "—",
    },
    {
      title: "LAST UPDATED",
      dataIndex: "last_modified",
      key: "last_modified",
      render: (value) => formatProjectStartDate(value),
    },
    {
      title: "",
      key: "action",
      width: 40,
      render: (_, record) => (
        <Link
          href={projectViewHref(record)}
          className="active-projects-table__row-arrow"
          aria-label={`Open ${record.name}`}
          onClick={() => handleProjectRowClick(record)}
        >
          <RightOutlined />
        </Link>
      ),
    },
  ];

  return (
    <div className="active-projects-page">
      <div className="active-projects-page__toolbar clients-page__toolbar">
        <div className="clients-page__filters">
          <Input.Search
            allowClear
            placeholder="Search clients, projects…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 260 }}
            aria-label="Search projects"
          />

          <Select
            value={clientFilter}
            onChange={setClientFilter}
            style={{ width: 180 }}
            aria-label="Filter by client"
            options={clientOptions.map((c) => ({ value: c, label: c }))}
          />

          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 160 }}
            aria-label="Filter by status"
            options={[
              { value: ALL_STATUSES, label: "All Statuses" },
              ...PROJECT_STATUS_OPTIONS.map((s) => ({
                value: s,
                label: STATUS_LABELS[s],
              })),
            ]}
          />

          <Select
            value={sortBy}
            onChange={(val) => setSortBy(val as SortOption)}
            style={{ width: 180 }}
            aria-label="Sort projects"
            options={(Object.keys(SORT_LABELS) as SortOption[]).map((key) => ({
              value: key,
              label: SORT_LABELS[key],
            }))}
          />
        </div>

        <div className="clients-page__meta">
          <span className="clients-page__count">
            Showing {filteredProjects.length} project
            {filteredProjects.length === 1 ? "" : "s"}
          </span>

          {canCreate && (
            <button
              className="clients-page__add-btn"
              onClick={() => setShowCreateModal(true)}
            >
              <PlusOutlined /> New Project
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="workspace__loading">
          <Spin size="large" />
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="clients-page__empty">
          <div className="clients-page__empty-icon">
            <FolderOpenOutlined />
          </div>
          <p className="clients-page__empty-title">
            {debouncedSearchQuery.trim() ||
            clientFilter !== ALL_CLIENTS ||
            statusFilter !== ALL_STATUSES
              ? `No projects found matching your filters`
              : "No projects yet"}
          </p>
          <p className="clients-page__empty-text">
            Try adjusting your search or filters, or create a new project.
          </p>
        </div>
      ) : (
        <AITable<ProjectRow>
          columns={columns}
          datasource={filteredProjects}
          rowKey={(record) => record.id}
          rowClassName={() => "active-projects-table__row"}
          pageSize={10}
        />
      )}

      {showCreateModal && (
        <CreateProjectModal
          existingNames={projects.map((p) => p.name)}
          onClose={() => setShowCreateModal(false)}
          onProjectCreated={handleProjectCreated}
        />
      )}
    </div>
  );
}
