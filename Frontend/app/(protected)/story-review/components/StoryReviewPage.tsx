"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { App, ConfigProvider, Select, Spin, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { SearchOutlined, CheckCircleOutlined } from "@ant-design/icons";
import AITable from "@/components/AITable";
import { PERMISSIONS } from "@/constants";
import { usePermissions } from "@/hooks/usePermissions";
import { decideStory, fetchReviewQueue } from "@/services/storyApprovalService";
import type {
  ReviewDecision,
  ReviewQueueCounts,
  ReviewQueueFacets,
  ReviewStory,
} from "@/types/storyApproval";
import "../assets/css/storyReview.css";

type Status = "Pending" | "Approved" | "Rejected";

const SELECT_THEME = {
  token: {
    colorPrimary: "#1f3333",
    controlOutline: "rgba(31, 51, 51, 0.1)",
    controlItemBgActive: "#eef2f2",
  },
};

const PRIORITY_TAG: Record<string, string> = {
  high: "error",
  medium: "warning",
  low: "success",
};

function priorityTagColor(value: string): string {
  return PRIORITY_TAG[value.trim().toLowerCase()] ?? "default";
}

const AVATAR_PALETTE = [
  { bg: "#dbeafe", color: "#1d4ed8" },
  { bg: "#dcfce7", color: "#15803d" },
  { bg: "#ede9fe", color: "#7c3aed" },
  { bg: "#fef3c7", color: "#b45309" },
  { bg: "#fee2e2", color: "#dc2626" },
];

function toStatus(raw: string): Status {
  const s = raw.toLowerCase();
  if (s === "approved") return "Approved";
  if (s === "rejected") return "Rejected";
  return "Pending";
}

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (Number.isNaN(d)) return "";
  if (d === 0) return "Today";
  if (d === 1) return "Yesterday";
  if (d < 7) return `${d}d ago`;
  if (d < 30) return `${Math.floor(d / 7)}w ago`;
  return `${Math.floor(d / 30)}mo ago`;
}

function formatDateTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function avatarColor(name: string) {
  const idx =
    name.split("").reduce((a, c) => a + c.charCodeAt(0), 0) %
    AVATAR_PALETTE.length;
  return AVATAR_PALETTE[idx];
}

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`sr-status-badge ${status}`}>
      {status === "Approved" && (
        <CheckCircleOutlined style={{ fontSize: 10 }} />
      )}
      {status}
    </span>
  );
}

const PAGE_SIZE = 20;

export default function StoryReviewPage() {
  // Viewing the queue only needs STORY_GET_PENDING_APPROVALS (the layout guard);
  // actually deciding needs STORY_APPROVE, which the backend enforces on the
  // decision endpoint. Gate the decision controls on it too so a view-only
  // reviewer sees a read-only queue instead of buttons that 403 on click.
  const { hasPermission } = usePermissions();
  const canApprove = hasPermission(PERMISSIONS.STORY_APPROVE);
  const { message } = App.useApp();

  const [stories, setStories] = useState<ReviewStory[]>([]);
  const [counts, setCounts] = useState<ReviewQueueCounts>({
    pending: 0,
    approved: 0,
    rejected: 0,
  });
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<ReviewQueueFacets>({
    projects: [],
    epics: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // `search` is the raw input; `debouncedSearch` is what actually drives the
  // server fetch, so typing doesn't fire a request per keystroke.
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  // Server-side filters: project/epic hold ids (not display names), status holds
  // the raw backend value ("pending"/"approved"/"rejected").
  const [projectFilter, setProjectFilter] = useState("");
  const [epicFilter, setEpicFilter] = useState("");
  // Default to pending so the queue shows only outstanding work; a decided story
  // drops out of the view on refetch. Approved/rejected stay as history one
  // filter-click away (the summary cards still count all statuses).
  const [statusFilter, setStatusFilter] = useState("pending");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [expandedId, setExpandedId] = useState("");
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Filtering and paging are server-side, so `load` just fetches the current
  // page with the active filters. A request-id guard drops stale responses when
  // filters change faster than the network. The effect raises the spinner, but
  // only the call that actually settles the view lowers it — a superseded
  // response clearing `loading` would paint the empty state over rows that are
  // still in flight.
  const reqId = useRef(0);
  const load = useCallback(async () => {
    const id = ++reqId.current;
    // Selection is per-view: every call here means a different filter, page or
    // search, so keeping the old keys would let "Approve all" fire at rows the
    // reviewer can no longer see.
    setSelectedRowKeys([]);
    try {
      const data = await fetchReviewQueue({
        status: statusFilter || undefined,
        projectId: projectFilter || undefined,
        epicId: epicFilter || undefined,
        search: debouncedSearch || undefined,
        page,
        pageSize,
      });
      // Superseded — the newer request owns the spinner and the view.
      if (id !== reqId.current) return;
      // Deciding the last item on a page (or a filter that shrinks the result
      // set) leaves the user stranded on a page that no longer exists — we own
      // `current`, so nothing else moves them off it. The page-1 refetch this
      // triggers owns the spinner from here.
      if (data.stories.length === 0 && page > 1) {
        setPage(1);
        return;
      }
      setStories(data.stories);
      setCounts(data.counts);
      setTotal(data.total);
      setFacets(data.facets);
      setError(null);
    } catch (err) {
      if (id !== reqId.current) return;
      setError(
        err instanceof Error ? err.message : "Failed to load the review queue.",
      );
    }
    setLoading(false);
  }, [
    statusFilter,
    projectFilter,
    epicFilter,
    debouncedSearch,
    page,
    pageSize,
  ]);

  useEffect(() => {
    setLoading(true);
    void load();
  }, [load]);

  // `busy` is state, so two clicks inside one render tick both read the stale
  // `false`; the ref is the guard that actually lands in time.
  const busyRef = useRef(false);
  const decide = useCallback(
    async (approvalIds: string[], decision: ReviewDecision) => {
      if (approvalIds.length === 0 || busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setError(null);
      try {
        const results = await Promise.allSettled(
          approvalIds.map((id) => decideStory(id, decision)),
        );
        const failures = results.filter(
          (r) => r.status === "rejected",
        ) as PromiseRejectedResult[];
        if (failures.length > 0) {
          const detail =
            failures[0].reason instanceof Error
              ? failures[0].reason.message
              : "Unknown error";
          setError(
            approvalIds.length === 1
              ? detail
              : `${failures.length} of ${approvalIds.length} decisions could not be recorded: ${detail}`,
          );
        }
        // The default Pending filter drops a decided story on the refetch, so
        // without this the row just vanishes with nothing to explain it.
        const succeeded = approvalIds.length - failures.length;
        if (succeeded > 0) {
          message.success(
            `${
              succeeded === 1 ? "Story" : `${succeeded} stories`
            } ${decision}.`,
          );
        }
        setSelectedRowKeys([]);
        await load();
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [load, message],
  );

  // Any filter/search change returns to page 1 so the user never lands on a page
  // beyond the new result set.
  const changeFilter = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };

  const projectOptions = facets.projects.map((p) => ({
    value: p.id,
    label: p.label,
  }));
  const epicOptions = facets.epics.map((e) => ({
    value: e.id,
    label: e.label,
  }));
  const isFiltered = !!(search || projectFilter || epicFilter || statusFilter);
  // Narrowing *beyond* the default pending view — drives the "no match" vs
  // "all caught up" empty state (an empty pending queue is a good thing, not a
  // failed search).
  const hasActiveNarrowing = !!(
    search ||
    projectFilter ||
    epicFilter ||
    (statusFilter && statusFilter !== "pending")
  );

  const columns: ColumnsType<ReviewStory> = [
    {
      title: "ID",
      dataIndex: "user_story_id",
      width: 118,
      render: (value: string) => <span className="sr-story-id">{value}</span>,
    },
    {
      title: "Story",
      key: "story",
      width: "40%",
      render: (_, r) => (
        <div className="sr-story-cell">
          <span className="sr-title-cell" title={r.title}>
            {r.title}
          </span>
          <span className="sr-muted sr-cell-sub">
            {[r.epic_title, r.project_name].filter(Boolean).join(" · ")}
          </span>
        </div>
      ),
    },
    {
      title: "Status",
      key: "status",
      width: 140,
      render: (_, r) => <StatusBadge status={toStatus(r.status)} />,
    },
    {
      title: "Priority",
      dataIndex: "priority",
      width: 90,
      render: (value: string | null) =>
        value ? (
          <Tag color={priorityTagColor(value)} style={{ width: "fit-content" }}>
            {value}
          </Tag>
        ) : (
          <span className="sr-muted">—</span>
        ),
    },
    {
      title: "Submitted by",
      key: "submittedBy",
      width: 160,
      render: (_, r) => {
        const av = avatarColor(r.submitted_by);
        return (
          <div className="sr-submitter">
            <span
              className="sr-avatar"
              style={{ background: av.bg, color: av.color }}
            >
              {initials(r.submitted_by)}
            </span>
            <span className="sr-submitter-name">{r.submitted_by}</span>
          </div>
        );
      },
    },
    {
      title: "Date",
      dataIndex: "submitted_at",
      width: 90,
      render: (value: string) => (
        <span className="sr-muted">{timeAgo(value)}</span>
      ),
    },
    {
      title: "Approved By",
      key: "approvedBy",
      width: 170,
      render: (_, r) => {
        const eff = toStatus(r.status);
        if (eff === "Pending") {
          return <span className="sr-muted">Pending</span>;
        }
        if (eff !== "Approved" || !r.decided_by_name) {
          return <span className="sr-muted">—</span>;
        }
        return (
          <div className="sr-story-cell">
            <span>{r.decided_by_name}</span>
            {r.decided_at && (
              <span className="sr-muted sr-cell-sub">
                {timeAgo(r.decided_at)}
              </span>
            )}
          </div>
        );
      },
    },
    // Decision column only for reviewers who can actually decide (STORY_APPROVE).
    ...(canApprove
      ? [
          {
            title: "Decision",
            key: "decision",
            width: 104,
            render: (_: unknown, r: ReviewStory) => {
              const eff = toStatus(r.status);
              return (
                <div className="sr-quick-actions">
                  <button
                    className={`sr-quick sr-quick--approve${
                      eff === "Approved" ? " is-active" : ""
                    }`}
                    title={
                      eff === "Pending"
                        ? "Approve"
                        : `Already ${eff.toLowerCase()}`
                    }
                    disabled={busy || eff !== "Pending"}
                    onClick={(e) => {
                      e.stopPropagation();
                      void decide([r.id], "approved");
                    }}
                  >
                    ✓
                  </button>
                  <button
                    className={`sr-quick sr-quick--reject${
                      eff === "Rejected" ? " is-active" : ""
                    }`}
                    title={
                      eff === "Pending"
                        ? "Reject"
                        : `Already ${eff.toLowerCase()}`
                    }
                    disabled={busy || eff !== "Pending"}
                    onClick={(e) => {
                      e.stopPropagation();
                      void decide([r.id], "rejected");
                    }}
                  >
                    ✕
                  </button>
                </div>
              );
            },
          },
        ]
      : []),
  ];

  function renderDetail(s: ReviewStory) {
    const eff = toStatus(s.status);
    const av = avatarColor(s.submitted_by);
    return (
      <div className="sr-detail">
        <div className="sr-detail-main">
          <div className="sr-story-card">
            <div className="sr-story-header">
              <span className="sr-story-key">{s.user_story_id}</span>
              <span className="sr-story-title">{s.title}</span>
            </div>
            <p className="sr-description">
              {s.description || "No description provided."}
            </p>
          </div>

          <div className="sr-ac-heading">Acceptance criteria</div>
          {s.acceptance_criteria.length > 0 ? (
            s.acceptance_criteria.map((ac, i) => (
              <div className="sr-ac-item" key={i}>
                <span className="sr-ac-check">✓</span>
                <span>{ac}</span>
              </div>
            ))
          ) : (
            <div className="sr-muted" style={{ fontSize: 12 }}>
              No acceptance criteria recorded.
            </div>
          )}
        </div>

        <div className="sr-detail-side">
          <div className="sr-panel-block">
            <div className="sr-panel-label">Current status</div>
            <StatusBadge status={eff} />
          </div>

          <div className="sr-panel-block">
            <div className="sr-panel-label">Submitted by</div>
            <div className="sr-panel-submitter">
              <span
                className="sr-avatar sr-avatar--lg"
                style={{ background: av.bg, color: av.color }}
              >
                {initials(s.submitted_by)}
              </span>
              <div>
                <div className="sr-panel-submitter-name">{s.submitted_by}</div>
                <div className="sr-panel-submitter-ago">
                  {timeAgo(s.submitted_at)}
                </div>
              </div>
            </div>
          </div>

          <div className="sr-panel-block">
            <div className="sr-panel-label">Approved by</div>
            {eff === "Approved" && s.decided_by_name ? (
              <div className="sr-panel-submitter">
                <span
                  className="sr-avatar sr-avatar--lg"
                  style={{
                    background: avatarColor(s.decided_by_name).bg,
                    color: avatarColor(s.decided_by_name).color,
                  }}
                >
                  {initials(s.decided_by_name)}
                </span>
                <div>
                  <div className="sr-panel-submitter-name">
                    {s.decided_by_name}
                  </div>
                  {s.decided_at && (
                    <div className="sr-panel-submitter-ago">
                      {formatDateTime(s.decided_at)}
                    </div>
                  )}
                </div>
              </div>
            ) : eff === "Pending" ? (
              <span className="sr-muted">Pending</span>
            ) : (
              <span className="sr-muted">—</span>
            )}
          </div>

          {canApprove && (
            <div className="sr-panel-block">
              <div className="sr-panel-label">Review decision</div>
              <div className="sr-decision-btns">
                <button
                  className={`sr-decision-btn sr-decision-btn--approve${
                    eff === "Approved" ? " is-active" : ""
                  }`}
                  disabled={busy || eff !== "Pending"}
                  onClick={() => void decide([s.id], "approved")}
                >
                  ✓ Approve
                </button>
                <button
                  className={`sr-decision-btn sr-decision-btn--reject${
                    eff === "Rejected" ? " is-active" : ""
                  }`}
                  disabled={busy || eff !== "Pending"}
                  onClick={() => void decide([s.id], "rejected")}
                >
                  ✕ Reject
                </button>
              </div>
              {eff !== "Pending" && (
                <div
                  className="sr-muted"
                  style={{ fontSize: 12, marginTop: 6 }}
                >
                  {eff} — this decision is final.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="sr-page">
      <div className="sr-content">
        <div className="sr-subheader">
          <span className="sr-subheader-text">
            Review and approve user stories before AI test case generation
          </span>
          <span className="sr-pending-pill">
            ◷ {counts.pending} pending review
          </span>
        </div>

        <section className="sr-summary" aria-label="Story review summary">
          <div className="sr-summary-item sr-summary-item--pending">
            <p>Pending</p>
            <strong>{counts.pending}</strong>
            <span>awaiting decision</span>
          </div>
          <div className="sr-summary-item sr-summary-item--approved">
            <p>Approved</p>
            <strong>{counts.approved}</strong>
            <span>ready for generation</span>
          </div>
          <div className="sr-summary-item sr-summary-item--rejected">
            <p>Rejected</p>
            <strong>{counts.rejected}</strong>
            <span>not proceeding</span>
          </div>
        </section>

        <section className="sr-filters" aria-label="Story filters">
          <label className="sr-search">
            <SearchOutlined />
            <input
              type="search"
              placeholder="Search by title or ID…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </label>

          <ConfigProvider theme={SELECT_THEME}>
            <Select
              aria-label="Project filter"
              className="sr-select"
              value={projectFilter}
              onChange={changeFilter(setProjectFilter)}
              options={[
                { label: "All projects", value: "" },
                ...projectOptions,
              ]}
            />
            <Select
              aria-label="Epic filter"
              className="sr-select"
              value={epicFilter}
              onChange={changeFilter(setEpicFilter)}
              options={[{ label: "All epics", value: "" }, ...epicOptions]}
            />
            <Select
              aria-label="Status filter"
              className="sr-select"
              value={statusFilter}
              onChange={changeFilter(setStatusFilter)}
              options={[
                { label: "All statuses", value: "" },
                { label: "Pending", value: "pending" },
                { label: "Approved", value: "approved" },
                { label: "Rejected", value: "rejected" },
              ]}
            />
          </ConfigProvider>

          {isFiltered && (
            <button
              className="sr-clear"
              onClick={() => {
                setSearch("");
                setProjectFilter("");
                setEpicFilter("");
                setStatusFilter("");
                setPage(1);
              }}
            >
              ✕ Clear
            </button>
          )}
          <div className="sr-spacer" />
          <span className="sr-count">{total} stories</span>
        </section>

        {selectedRowKeys.length > 0 && (
          <div className="sr-bulk">
            <span className="sr-bulk-count">
              {selectedRowKeys.length} selected
            </span>
            <div className="sr-bulk-sep" />
            <button
              className="sr-bulk-btn sr-bulk-btn--approve"
              disabled={busy}
              onClick={() => void decide(selectedRowKeys, "approved")}
            >
              ✓ Approve all
            </button>
            <button
              className="sr-bulk-btn sr-bulk-btn--reject"
              disabled={busy}
              onClick={() => void decide(selectedRowKeys, "rejected")}
            >
              ✕ Reject all
            </button>
            <div className="sr-spacer" />
            <button
              className="sr-bulk-clear"
              onClick={() => setSelectedRowKeys([])}
            >
              ✕ Clear
            </button>
          </div>
        )}

        <div className="sr-table-wrap">
          {loading ? (
            <div className="sr-empty">
              <Spin />
              <div className="sr-empty-sub" style={{ marginTop: 12 }}>
                Loading your review queue…
              </div>
            </div>
          ) : error ? (
            <div className="sr-empty">
              <div className="sr-empty-title">
                Couldn’t load the review queue
              </div>
              <div className="sr-empty-sub">{error}</div>
            </div>
          ) : stories.length === 0 ? (
            <div className="sr-empty">
              <div className="sr-empty-icon">◫</div>
              <div className="sr-empty-title">
                {hasActiveNarrowing
                  ? "No stories found"
                  : "You’re all caught up"}
              </div>
              <div className="sr-empty-sub">
                {hasActiveNarrowing
                  ? "Try adjusting your filters or search query"
                  : "No stories are awaiting your review."}
              </div>
            </div>
          ) : (
            <AITable<ReviewStory>
              rowKey="id"
              columns={columns}
              datasource={stories}
              // Dims the table and spins while a decision is in flight — the
              // buttons go disabled either way, but nothing else showed progress.
              loading={busy}
              pagination={{
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                placement: ["bottomCenter"],
                onChange: (nextPage, nextSize) => {
                  setPage(nextPage);
                  setPageSize(nextSize);
                },
              }}
              rowSelection={
                canApprove
                  ? {
                      selectedRowKeys,
                      onChange: (keys) => setSelectedRowKeys(keys as string[]),
                      // Decisions are final, so a decided row can't be bulk-
                      // actioned — disable its checkbox instead of letting the
                      // batch 409 on it.
                      getCheckboxProps: (record) => ({
                        disabled: toStatus(record.status) !== "Pending",
                      }),
                    }
                  : undefined
              }
              rowClassName={(record) =>
                `sr-data-row${
                  expandedId === record.id ? " sr-data-row--expanded" : ""
                }`
              }
              expandable={{
                expandedRowKeys: expandedId ? [expandedId] : [],
                expandRowByClick: true,
                showExpandColumn: false,
                onExpand: (expanded, record) =>
                  setExpandedId(expanded ? record.id : ""),
                expandedRowRender: (record) => renderDetail(record),
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
