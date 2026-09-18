"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Breadcrumb, App, Spin, Input } from "antd";
import { HomeOutlined, PlusOutlined } from "@ant-design/icons";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import Link from "next/link";
import { Client } from "@/types/client";
import { Programme } from "@/types/programme";
import { getClientByName } from "@/services/clientsService";
import {
  listProgrammesByClientId,
  deleteProgrammeById,
} from "@/services/programmeService";
import ProgrammeSection from "./ProgrammeSection";
import ProgrammeListView from "./ProgrammeListView";
import AddProgrammeModal from "./AddProgrammeModal";
import EditProgrammeModal from "./EditProgrammeModal";
import DeleteProgrammePopup from "./DeleteProgrammePopup";
import "../../assets/css/clients.css";
import DocumentsSection from "@/app/(protected)/clients/components/DocumentsSection";
import { useDebounce } from "@/lib/useDebounce";
import ViewToggle, { ViewMode } from "@/components/ViewToggle";

interface ClientWorkspacePageProps {
  clientName: string;
}

export default function ClientWorkspacePage({
  clientName,
}: ClientWorkspacePageProps) {
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const canCreateProgramme = hasPermission(PERMISSIONS.PROGRAMME_CREATE);

  const [client, setClient] = useState<Client | null>(null);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("card");

  const [showAddProgramme, setShowAddProgramme] = useState(false);
  const [editingProgramme, setEditingProgramme] = useState<Programme | null>(
    null,
  );
  const [deletingProgramme, setDeletingProgramme] = useState<Programme | null>(
    null,
  );

  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const clientData = await getClientByName(clientName);
      setClient(clientData);
      const programmeDetails = await listProgrammesByClientId(clientData.id);
      setProgrammes(programmeDetails);
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Failed to load client workspace.";
      setPageError(msg);
      message.error({ key: "workspace-load-error", content: msg });
    } finally {
      setLoading(false);
    }
  }, [clientName]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const filteredProgrammes = useMemo(() => {
    const q = debouncedSearchQuery.trim().toLowerCase();
    if (!q) return programmes;
    return programmes.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q) ||
        p.status.toLowerCase().includes(q),
    );
  }, [programmes, debouncedSearchQuery]);

  function handleProgrammeAdded(programme: Programme) {
    setProgrammes((prev) => [...prev, programme]);
    message.success(`Programme "${programme.name}" created successfully.`);
  }

  function handleProgrammeUpdated(updated: Programme) {
    setProgrammes((prev) =>
      prev.map((p) => (p.id === updated.id ? updated : p)),
    );
    message.success(`Programme "${updated.name}" updated successfully.`);
  }

  function handleProgrammeDeleted(deletedId: string) {
    setProgrammes((prev) => prev.filter((p) => p.id !== deletedId));
    message.success("Programme deleted successfully.");
  }

  const displayName = client?.name ?? clientName;

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
        <span className="workspace__breadcrumb-current">{displayName}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="workspace">
        <div className="workspace__loading">
          <Spin size="large" description="Loading workspace…" />
        </div>
      </div>
    );
  }

  const emptyMessage =
    searchQuery.trim() !== ""
      ? `No programmes found matching "${searchQuery.trim()}"`
      : "No programmes yet";
  const emptySubtext =
    searchQuery.trim() !== ""
      ? "Try a different search term."
      : "Add the first programme to get started.";

  return (
    <div className="workspace">
      {/* Breadcrumb */}
      <div className="workspace__breadcrumb-bar">
        <Breadcrumb items={breadcrumbItems} separator="›" />
      </div>

      {/* Compact page header */}
      <div className="workspace__compact-header">
        <h1 className="workspace__compact-title">{displayName}</h1>
        {client && (
          <div className="workspace__meta">
            <span className="workspace__meta-item">{client.industry}</span>
            <span className="workspace__meta-dot" />
            <span className="workspace__meta-item">{client.location}</span>
            <span className="workspace__meta-dot" />
            <span className="workspace__meta-item">
              {programmes.length} programme{programmes.length !== 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>

      <DocumentsSection folderPath={`${clientName}`} entityId={client!.id} />

      {/* Section header: title + count, search, view toggle, add button — all on one line */}
      <div className="workspace__section-header">
        <h2 className="workspace__section-title">
          Programmes
          {programmes.length > 0 && (
            <span className="workspace__section-count">
              {filteredProgrammes.length}
            </span>
          )}
        </h2>

        <div className="workspace__section-actions">
          {programmes.length > 0 && (
            <Input.Search
              allowClear
              placeholder="Search programmes…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 240 }}
              aria-label="Search programmes"
            />
          )}

          {programmes.length > 0 && (
            <ViewToggle viewMode={viewMode} onChange={setViewMode} />
          )}

          {client && canCreateProgramme && (
            <button
              className="workspace__add-btn"
              onClick={() => setShowAddProgramme(true)}
            >
              <PlusOutlined className="btn-icon" />
              Add Programme
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="workspace__body">
        {pageError && programmes.length === 0 ? (
          <div className="workspace__error-state">
            <div className="workspace__error-icon">⚠</div>
            <p className="workspace__error-title">Failed to load workspace</p>
            <p className="workspace__error-text">{pageError}</p>
            <Link href="/clients" className="workspace__back-link">
              ← Back to Clients
            </Link>
          </div>
        ) : filteredProgrammes.length === 0 ? (
          <div className="workspace__empty">
            <div className="workspace__empty-icon">📋</div>
            <p className="workspace__empty-title">{emptyMessage}</p>
            <p className="workspace__empty-text">{emptySubtext}</p>
          </div>
        ) : viewMode === "card" ? (
          <div className="workspace__programmes">
            {filteredProgrammes.map((programme) => (
              <ProgrammeSection
                key={programme.id}
                programme={programme}
                clientName={clientName}
                clientManager={client?.manager}
                onEdit={() => setEditingProgramme(programme)}
                onDelete={() => setDeletingProgramme(programme)}
              />
            ))}
          </div>
        ) : (
          <ProgrammeListView
            programmes={filteredProgrammes}
            clientName={clientName}
            onEdit={(p) => setEditingProgramme(p)}
            onDelete={(p) => setDeletingProgramme(p)}
          />
        )}
      </div>

      {showAddProgramme && client && (
        <AddProgrammeModal
          clientId={client.id}
          clientDisplayName={displayName}
          existingNames={programmes.map((p) => p.name)}
          onClose={() => setShowAddProgramme(false)}
          onAdd={(prog) => {
            handleProgrammeAdded(prog);
            setShowAddProgramme(false);
          }}
        />
      )}

      {editingProgramme && (
        <EditProgrammeModal
          programme={editingProgramme}
          existingNames={programmes
            .filter((p) => p.id !== editingProgramme.id)
            .map((p) => p.name)}
          onClose={() => setEditingProgramme(null)}
          onUpdated={(updated) => {
            handleProgrammeUpdated(updated);
            setEditingProgramme(null);
          }}
        />
      )}

      {deletingProgramme && (
        <DeleteProgrammePopup
          programme={deletingProgramme}
          onClose={() => setDeletingProgramme(null)}
          onDeleted={(deletedId) => {
            handleProgrammeDeleted(deletedId);
            setDeletingProgramme(null);
          }}
        />
      )}
    </div>
  );
}
