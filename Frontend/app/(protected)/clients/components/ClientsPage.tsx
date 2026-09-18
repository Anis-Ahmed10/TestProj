"use client";

import { useEffect, useMemo, useState } from "react";
import { PlusOutlined, UserOutlined } from "@ant-design/icons";
import { Select, Input, App } from "antd";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";
import { useAppSelector } from "@/store/store";
import {
  ALL_INDUSTRIES,
  Client,
  CLIENT_STATUS_OPTIONS,
  IndustryType,
} from "@/types/client";
import AddClientModal from "./AddClientModal";
import ClientCard from "./ClientCard";
import ClientListView from "./ClientListView";
import EditClientModal from "./EditClientModal";
import DeleteClientPopup from "./DeleteClientPopup";
import "../assets/css/clients.css";
import { useDebounce } from "@/lib/useDebounce";
import { fetchClients } from "@/services/clientsService";
import { getFriendlyClientBackendErrorMessage } from "@/utils/clients/clientsHelpers";

import ViewToggle, { ViewMode } from "@/components/ViewToggle";

export default function ClientsPage() {
  const { message } = App.useApp();
  const user = useAppSelector((state) => state.auth?.user);
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission(PERMISSIONS.CLIENT_CREATE);

  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>("card");

  type IndustryFilter = IndustryType | typeof ALL_INDUSTRIES;

  const [industryFilter, setIndustryFilter] =
    useState<IndustryFilter>(ALL_INDUSTRIES);

  const [statusFilter, setStatusFilter] = useState<
    (typeof CLIENT_STATUS_OPTIONS)[number] | ""
  >("");

  const [showModal, setShowModal] = useState(false);
  const [editingClientName, setEditingClientName] = useState<string | null>(
    null,
  );
  const [deletingClient, setDeletingClient] = useState<Client | null>(null);

  // Local search state — scoped to this page only, not a global header search
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  useEffect(() => {
    const loadClients = async () => {
      try {
        const fetchedClients = await fetchClients();
        setClients(fetchedClients);
      } catch (error) {
        message.error({
          key: "clients-load-error",
          content: getFriendlyClientBackendErrorMessage(null, null, "fetch"),
        });
      } finally {
        setLoading(false);
      }
    };

    loadClients();
  }, []);

  const industries = useMemo(() => {
    const uniqueIndustries = Array.from(
      new Set(clients.map((client) => client.industry)),
    );
    return [ALL_INDUSTRIES, ...uniqueIndustries] as const;
  }, [clients]);

  const filtered = useMemo(() => {
    const q = debouncedSearchQuery.trim().toLowerCase();
    return clients.filter((c) => {
      const matchIndustry =
        industryFilter === ALL_INDUSTRIES || c.industry === industryFilter;
      const matchStatus = statusFilter === "" || c.status === statusFilter;
      const matchSearch =
        q === "" ||
        c.name.toLowerCase().includes(q) ||
        c.industry.toLowerCase().includes(q);

      return matchIndustry && matchStatus && matchSearch;
    });
  }, [clients, industryFilter, statusFilter, debouncedSearchQuery]);

  function handleAdd(client: Client) {
    setClients((prev) => [client, ...prev]);
  }

  const emptyMessage =
    searchQuery.trim() !== ""
      ? `No clients found matching "${searchQuery.trim()}"`
      : "No clients found";

  const emptySubtext =
    searchQuery.trim() !== ""
      ? "Try a different search term or clear your filters."
      : "Try adjusting your filters or add a new client.";

  if (loading) {
    return (
      <div className="clients-page">
        <div className="workspace__loading">
          <div className="workspace__loading-spinner" />
          <span className="workspace__loading-text">Loading clients…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="clients-page">
      <div className="clients-page__toolbar">
        <div className="clients-page__filters">
          <Input.Search
            allowClear
            placeholder="Search clients, industry…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 280 }}
            aria-label="Search clients"
          />

          <Select
            value={industryFilter}
            onChange={(val) => setIndustryFilter(val as IndustryFilter)}
            style={{ width: 160 }}
            aria-label="Filter by industry"
            options={industries.map((ind) => ({ value: ind, label: ind }))}
          />

          <Select
            value={statusFilter}
            onChange={(val) => setStatusFilter(val)}
            style={{ width: 160 }}
            aria-label="Filter by status"
            options={
              [
                { value: "", label: "All Statuses" },
                ...CLIENT_STATUS_OPTIONS.map((status) => ({
                  value: status,
                  label: status,
                })),
              ] as {
                value: (typeof CLIENT_STATUS_OPTIONS)[number] | "";
                label: string;
              }[]
            }
          />
        </div>

        <div className="clients-page__meta">
          <span className="clients-page__count">
            {filtered.length} active client{filtered.length === 1 ? "" : "s"}
          </span>

          {/* View toggle */}
          <ViewToggle viewMode={viewMode} onChange={setViewMode} />

          {canCreate && (
            <button
              className="clients-page__add-btn"
              onClick={() => setShowModal(true)}
            >
              <PlusOutlined /> Add Client
            </button>
          )}
        </div>
      </div>

      {/* Card view */}
      {viewMode === "card" && (
        <div className="clients-page__grid">
          {filtered.length > 0 ? (
            filtered.map((client) => (
              <ClientCard
                key={client.id}
                client={client}
                onEdit={() => {
                  setDeletingClient(null);
                  setEditingClientName(client.name);
                }}
                onDelete={() => {
                  setEditingClientName(null);
                  setDeletingClient(client);
                }}
              />
            ))
          ) : (
            <div className="clients-page__empty">
              <div className="clients-page__empty-icon">
                <UserOutlined />
              </div>
              <p className="clients-page__empty-title">{emptyMessage}</p>
              <p className="clients-page__empty-text">{emptySubtext}</p>
            </div>
          )}
        </div>
      )}

      {/* List view */}
      {viewMode === "list" && (
        <>
          {filtered.length > 0 ? (
            <ClientListView
              clients={filtered}
              onEdit={(client) => {
                setDeletingClient(null);
                setEditingClientName(client.name);
              }}
              onDelete={(client) => {
                setEditingClientName(null);
                setDeletingClient(client);
              }}
            />
          ) : (
            <div className="clients-page__empty clients-page__empty--list">
              <div className="clients-page__empty-icon">
                <UserOutlined />
              </div>
              <p className="clients-page__empty-title">{emptyMessage}</p>
              <p className="clients-page__empty-text">{emptySubtext}</p>
            </div>
          )}
        </>
      )}

      {showModal && (
        <AddClientModal onClose={() => setShowModal(false)} onAdd={handleAdd} />
      )}

      {editingClientName && (
        <EditClientModal
          clientName={editingClientName}
          visible={true}
          onClose={() => setEditingClientName(null)}
          onUpdated={async () => {
            try {
              const refreshedClients = await fetchClients();
              setClients(refreshedClients);
            } catch {
              message.error({
                key: "clients-refresh-error",
                content:
                  "Client updated, but the client list could not be refreshed.",
              });
            }
          }}
          onDeleted={(deletedName) => {
            setClients((prev) => prev.filter((c) => c.name !== deletedName));
          }}
        />
      )}

      {deletingClient && (
        <DeleteClientPopup
          client={deletingClient}
          onClose={() => setDeletingClient(null)}
          onDeleted={(deletedName) => {
            setClients((prev) => prev.filter((c) => c.name !== deletedName));
            setDeletingClient(null);
          }}
        />
      )}
    </div>
  );
}
